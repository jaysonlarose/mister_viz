// debug: gcc -g -DDEBUG -o mister_viz_server mister_viz_server.c `pkg-config --cflags --libs libudev`
// gcc -Wall -O2 -s -o mister_viz_server mister_viz_server.c `pkg-config --cflags --libs libudev`

#include <stdio.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <sys/time.h>
#include <libudev.h>
#include <string.h>
#include <libgen.h>
#include <fcntl.h>
#include <linux/input.h>
#include <stdint.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/poll.h>
#include <stdbool.h>

#define SOCKET_BINDPORT 22101
#define SOCKET_BINDHOST ""

#define FD_TYPE_UNDEFINED    0
#define FD_TYPE_UDEV         1
#define FD_TYPE_INPUT        2
#define FD_TYPE_LISTENSOCKET 3
#define FD_TYPE_CLIENTSOCKET 4

typedef struct deviceinfo {
	char *name;
	uint8_t type;
	uint16_t vendor_id;
	uint16_t product_id;
} deviceinfo;

typedef struct pollpool {
	nfds_t len;
	struct udev *udev_context;
	struct udev_monitor *monitor;
	struct pollfd *pool;
	struct deviceinfo *info;
} pollpool;

pollpool *pollpool_create(void) {
	pollpool *ret = (pollpool *) malloc(sizeof(pollpool));
	ret->len = 0;
	ret->pool = NULL;
	ret->info = NULL;
	return ret;
}

void pollpool_destroy(pollpool *pool) {
	nfds_t i;
	if (pool->pool != NULL) {
		for (i = 0; i < pool->len; i++) {
			if (pool->pool[i].fd >= 0) {
				close(pool->pool[i].fd);
			}
		}
		free(pool->pool);
	}
	if (pool->info != NULL) {
		for (i = 0; i < pool->len; i++) {
			if (pool->info[i].name != NULL) {
				free(pool->info[i].name);
			}
		}
		free(pool->info);
	}
	free(pool);
}

nfds_t pollpool_add(pollpool *pool) {
	/* Adds a new blank entry into the pool struct. */
	/* Returns the index number for the new entry. */
	nfds_t idx = pool->len;
	pool->pool = (struct pollfd *) realloc(pool->pool, sizeof(struct pollfd) * (pool->len + 1));
	pool->info = (deviceinfo *) realloc(pool->info, sizeof(deviceinfo) * (pool->len + 1));
	pool->len++;

	pool->pool[idx].fd = -1;
	pool->pool[idx].events = 0;
	pool->pool[idx].revents = 0;
	pool->info[idx].name = NULL;
	pool->info[idx].type = FD_TYPE_UNDEFINED;
	//struct pollfd *ret = (&(pool->pool))[pool->len - 1];
	//memset(ret, -1, sizeof(struct pollfd));
	//deviceinfo *info = pool->info[pool->len - 1];
	//info->name = NULL;
	//memset(pool->pool[pool->len - 1], 0, sizeof(struct pollfd));

	//struct pollfd *ret = pool->pool[pool->len - 1];
	return idx;
}

void pollpool_remove(pollpool *pool, nfds_t idx) {
	/* Removes entry at index `idx` from the pool struct. */
	/* Items occurring past this entry will be moved to fill in the gap. */
	if (pool->pool[idx].fd >= 0) {
		//printf("closing fd %d\n", pool->pool[idx].fd);
		close(pool->pool[idx].fd);
	}
	if (pool->info[idx].name != NULL) {
		free(pool->info[idx].name);
	}
	for (nfds_t i = idx; i < (pool->len - 1); i++) {
		//printf("shuffling idx %ld to %ld\n", i+1, i);
		memcpy(&(pool->pool[i]), &(pool->pool[i+1]), sizeof(struct pollfd));
		memcpy(&(pool->info[i]), &(pool->info[i+1]), sizeof(deviceinfo));
	}
	pool->len--;
	//printf("Realloccing pool to size %ld\n", sizeof(struct pollfd *) * pool->len);
	pool->pool = (struct pollfd *) realloc(pool->pool, sizeof(struct pollfd) * pool->len);
	//printf("Reallocing info to size %ld\n", sizeof(deviceinfo) * pool->len);
	pool->info = (deviceinfo *) realloc(pool->info, sizeof(deviceinfo) * pool->len);
}

void pollpool_print(pollpool *pool) {
	printf("Poll pool contains %ld items:\n", pool->len);
	for (nfds_t i = 0; i < pool->len; i++) {
		//struct pollfd *p = (&(pool->pool))[i];
		printf("  item %ld:\n", i);
		printf("    fd: %d\n", pool->pool[i].fd);
		printf("    name: %s\n", pool->info[i].name);
	}
	printf("\n");
}

struct __attribute__((__packed__)) input_socket_packet {
	uint8_t opcode;
	uint8_t index;
	uint8_t player_id;
	uint16_t vendor_id;
	uint16_t product_id;
	uint16_t type;
	uint16_t code;
	uint32_t value;
	uint32_t tv_sec;
	uint32_t tv_usec;
};	

#define OP_INPUT 0
#define OP_PING  1
#define OP_PONG  2

void input_socket_send(pollpool *pool, uint16_t vid, uint16_t pid, struct input_event *ev) {
	struct input_socket_packet packet;
	packet.opcode = OP_INPUT;
	packet.index  = 0;
	packet.player_id = 0;
	packet.vendor_id = vid;
	packet.product_id = pid;
	packet.type = ev->type;
	packet.code = ev->code;
	packet.value = ev->value;
	packet.tv_sec = ev->time.tv_sec;
	packet.tv_usec = ev->time.tv_usec;

	for (nfds_t i = 0; i < pool->len; i++) {
		if (pool->info[i].type == FD_TYPE_CLIENTSOCKET) {
			write(pool->pool[i].fd, (char *) &packet, sizeof(packet));
		}
	}
}

void handle_udev_device(pollpool *pool, struct udev_device *udevice) {
	const char *devnode = udev_device_get_devnode(udevice);

	if (devnode != NULL) {
		//printf("devnode: %s\n", devnode);
		//const char *devpath = udev_device_get_devpath(udevice);
		//printf("devpath: %s\n", devpath);

		//const char *devtype = udev_device_get_devtype(udevice);
		//printf("devtype: %s\n", devtype);

		char *devnode_base = basename((char *) devnode);

		if (strncmp(devnode_base, "event", 5) == 0) {
			//printf("devnode_base: %s\n", devnode_base);
			//printf("%p\n", devnode);
			//printf("%p\n", devnode_base);
			//printf("woo\n");
			int fd = open(devnode, O_RDWR | O_CLOEXEC);
			if (fd > 0) {
				struct input_id dev_id;
				memset(&dev_id, 0, sizeof(dev_id));
				ioctl(fd, EVIOCGID, &dev_id);
				//printf("Could open\n");
				uint16_t vid = dev_id.vendor;
				uint16_t pid = dev_id.product;
				//printf("vendorid: %04x\n", vid);
				//printf("productid: %04x\n", pid);


				//struct pollfd *pollslot = pollpool_add(pool);
				nfds_t idx = pollpool_add(pool);
				struct pollfd *pollslot = &(pool->pool[idx]);
				deviceinfo *infoslot    = &(pool->info[idx]);

				//printf("Pollslot fd: %d\n", pollslot->fd);
				//printf("Pollslot fd: %d\n", pool->pool[idx].fd);
				pollslot->fd = fd;
				pollslot->events = POLLIN;
				//printf("Pollslot fd: %d\n", pollslot->fd);
				//printf("Pollslot fd: %d\n", pool->pool[idx].fd);
				infoslot->vendor_id = vid;
				infoslot->product_id = pid;

				char devname_temp[255];
				if (ioctl(fd, EVIOCGNAME(255 - 1), &devname_temp) < 1) {
					devname_temp[0] = '\0';
				}
				infoslot->name = strdup(devname_temp);
				//printf("device name: %s\n", infoslot->name);
				//printf("device name strlen: %ld\n", strlen(infoslot->name));
				//printf("device name: %s\n", pool->info[idx].name);
				printf("Adding input device: %s\n", pool->info[idx].name);

				infoslot->type = FD_TYPE_INPUT;
				
				//close(fd);
				//pollpool_print(pool);

			}
		}

		//const char *driver = udev_device_get_driver(udevice);
		//printf("driver: %s\n", driver);

		//const char *sysname = udev_device_get_sysname(udevice);
		//printf("sysname: %s\n", sysname);


	}
	//printf("\n");
}

void check_input(pollpool *pool) {
	int return_value = poll(pool->pool, pool->len, -1);
	//printf("poll return value: %d\n", return_value);
	if (return_value > 0) {
		for (nfds_t i = 0; i < pool->len; i++) {
			//printf("slot %ld type %d revents %d\n", i, pool->info[i].type, pool->pool[i].revents);
			switch(pool->info[i].type) {
				case FD_TYPE_UDEV:
					if (pool->pool[i].revents > 0) {
						//printf("Udev has something to say! revents: %d\n", pool->pool[i].revents);
					}
					if (pool->pool[i].revents & POLLIN) {
						pool->pool[i].revents &= ~POLLIN;
						struct udev_device *udevice = udev_monitor_receive_device(pool->monitor);
						if (udevice) {
							if (strcmp(udev_device_get_action(udevice), "add") == 0) {
								handle_udev_device(pool, udevice);
							}
							//printf("  action: %s, devnode: %s, subsystem: %s\n", udev_device_get_action(udevice), udev_device_get_devnode(udevice), udev_device_get_subsystem(udevice));
							udev_device_unref(udevice);
						}
					}
					break;
				case FD_TYPE_INPUT:
					bool do_print = false;
					if (pool->pool[i].revents > 0) {
						do_print = true;
					}
					if (do_print) {
						//printf("Device %ld (%s) revents: %d\n", i, pool->info[i].name, pool->pool[i].revents);
					}
					if (pool->pool[i].revents & POLLIN) {
						//printf("  POLLIN\n");
						pool->pool[i].revents &= ~POLLIN;
						struct input_event ev;
						memset(&ev, 0, sizeof(ev));
						if (read(pool->pool[i].fd, &ev, sizeof(ev)) == sizeof(ev)) {
							//printf("  %ld.%06ld: read event!\n", ev.time.tv_sec, ev.time.tv_usec);
							input_socket_send(pool, pool->info[i].vendor_id, pool->info[i].product_id, &ev);
						}
					}
					if (pool->pool[i].revents > 0) {
						printf("  UNKNOWN EVENT (revents: %d)\n", pool->pool[i].revents);
					}
					if (pool->pool[i].revents & POLLHUP) {
						printf("  POLLHUP\n");
						pollpool_remove(pool, i);
						i--;  // careful, modifying i here!
					}
					break;
				case FD_TYPE_LISTENSOCKET:
					if (pool->pool[i].revents & POLLIN) {
						pool->pool[i].revents &= ~POLLIN;
						//printf("Accepting socket\n");
						int client = accept(pool->pool[i].fd, NULL, NULL);
						nfds_t idx = pollpool_add(pool);
						pool->pool[idx].fd = client;
						pool->pool[idx].events = POLLIN;
						pool->info[idx].type = FD_TYPE_CLIENTSOCKET;
						/* Get the remote peer address */
						struct sockaddr_in remote_addr;
						socklen_t addr_len = sizeof(remote_addr);
						if (getpeername(pool->pool[idx].fd, (struct sockaddr *)&remote_addr, &addr_len) == 0) {
							char ip_str[INET_ADDRSTRLEN];
							inet_ntop(AF_INET, &(remote_addr.sin_addr), ip_str, INET_ADDRSTRLEN);
							//printf("Remote IP: %s, Port: %d\n", ip_str, ntohs(remote_addr.sin_port));
							char remote_peer_str[256];
							snprintf(remote_peer_str, 255, "%s:%d", ip_str, ntohs(remote_addr.sin_port));
							pool->info[idx].name = strdup(remote_peer_str);
						} else {
							//printf("Getpeername failed\n");
							pool->info[idx].name = strdup("client socket");
						}
						printf("Connected: %s\n", pool->info[idx].name);

					}
					if (pool->pool[i].revents > 0) {
						printf("Unhandled revents for listen socket: %d\n", pool->pool[i].revents);
					}
					break;
				case FD_TYPE_CLIENTSOCKET:
					bool do_close = false;
					if (pool->pool[i].revents & POLLIN) {
						pool->pool[i].revents &= ~POLLIN;
						char trash[1];
						int rlen = read(pool->pool[i].fd, trash, 1);
						if (rlen == 0) {
							do_close = true;
						} else {
							uint8_t opcode = trash[0];
							if (opcode == OP_PING) {
								trash[0] = OP_PONG;
								write(pool->pool[i].fd, (char *) trash, 1);
							} else {
								printf("Unknown opcode %d from %s, dropping client\n", opcode, pool->info[i].name);
								do_close = true;
							}
						}
					}
					if (pool->pool[i].revents & (POLLERR | POLLHUP | POLLNVAL)) {
						do_close = true;
						pool->pool[i].revents &= ~(POLLERR | POLLHUP | POLLNVAL);
					}
					if (pool->pool[i].revents > 0) {
						printf("Unhandled events for client %s: %d\n", pool->info[i].name, pool->pool[i].revents);
					}
					if (do_close) {
						printf("closing socket %ld\n", i);
						shutdown(pool->pool[i].fd, SHUT_RDWR);
						pollpool_remove(pool, i);
						i--; // careful, modifying i here!
					}
					break;

				default:
					break;
			}
		}
	}
}

int main(int argc, char **argv) {
	pollpool *pool = pollpool_create();
	pool->udev_context = udev_new();

	struct udev_enumerate *enumerator = udev_enumerate_new(pool->udev_context);

	udev_enumerate_add_match_subsystem(enumerator, "input");
	//int result = udev_enumerate_scan_devices(enumerator);
	udev_enumerate_scan_devices(enumerator);
	//fprintf(stderr, "udev_enumerate_scan_devices() result: %d\n", result);



	nfds_t udev_idx = pollpool_add(pool);
	//printf("Using idx %ld for udev\n", udev_idx);
	pool->info[udev_idx].name = strdup("udev monitor");
	pool->info[udev_idx].type = FD_TYPE_UDEV;

	//pollpool_print(pool);

	struct udev_list_entry *udev_entry = udev_enumerate_get_list_entry(enumerator);
	while (udev_entry != NULL) {
		const char *syspath = udev_list_entry_get_name(udev_entry);
		struct udev_device *udevice = udev_device_new_from_syspath(pool->udev_context, syspath);
		//printf("%s\n", syspath);
		handle_udev_device(pool, udevice);
		udev_device_unref(udevice);
		udev_entry = udev_list_entry_get_next(udev_entry);
	}

	udev_enumerate_unref(enumerator);

	pool->monitor = udev_monitor_new_from_netlink(pool->udev_context, "udev");
	if (!pool->monitor) {
		fprintf(stderr, "Failed to create udev monitor!\n");
		return EXIT_FAILURE;
	}
	if (udev_monitor_filter_add_match_subsystem_devtype(pool->monitor, "input", NULL) < 0) {
		fprintf(stderr, "Failed to add subsystem filter to udev monitor!\n");
		return EXIT_FAILURE;
	}
	if (udev_monitor_enable_receiving(pool->monitor) < 0) {
		fprintf(stderr, "Failed to enable receiving on udev monitor!\n");
		return EXIT_FAILURE;
	}

	pool->pool[udev_idx].fd = udev_monitor_get_fd(pool->monitor);
	pool->pool[udev_idx].events = POLLIN;

	/* Socket Initialization */
	int port = SOCKET_BINDPORT;
	struct sockaddr_in addr;
	struct hostent *host;
	bzero(&addr, sizeof(addr));
	addr.sin_family = AF_INET;
	addr.sin_port = htons(port);
	if (strlen(SOCKET_BINDHOST) == 0) {
		addr.sin_addr.s_addr = INADDR_ANY;
	} else {
		host = gethostbyname(SOCKET_BINDHOST);
		bcopy((char *) host->h_addr, (char *) &addr.sin_addr.s_addr, host->h_length);
	}
	int reuse = 1;
	int sock = socket(AF_INET, SOCK_STREAM | SOCK_NONBLOCK, 0);
	if (setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, (const char *) &reuse, sizeof(reuse)) < 0) {
		printf("can't setsockopt\n");
		return EXIT_FAILURE;
	}
	if (bind(sock, (struct sockaddr *) &addr, sizeof(addr)) != 0) {
		printf("can't bind port\n");
		return EXIT_FAILURE;
	}
	if (listen(sock, 1) != 0) {
		printf("can't listen to port\n");
		return EXIT_FAILURE;
	}
	nfds_t listensock_idx = pollpool_add(pool);
	printf("Using idx %ld for listen socket\n", listensock_idx);
	pool->pool[listensock_idx].fd   = sock;
	pool->pool[listensock_idx].events = POLLIN;
	pool->info[listensock_idx].name = strdup("listen socket");
	pool->info[listensock_idx].type = FD_TYPE_LISTENSOCKET;

	printf("Listening on port %d\n", port);
	printf("  sizeof struct timeval: %ld\n", sizeof(struct timeval));
	printf("  sizeof struct input_event: %ld\n", sizeof(struct input_event));
	printf("  sizeof struct input_socket_packet: %ld\n", sizeof(struct input_socket_packet));

	while (true) {
		check_input(pool);
	}


	udev_unref(pool->udev_context);

	pollpool_destroy(pool);
	return 0;
}
