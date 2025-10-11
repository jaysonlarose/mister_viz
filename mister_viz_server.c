// debug: gcc -g -DDEBUG -o mister_viz_server mister_viz_server.c `pkg-config --cflags --libs libudev`
// gcc -Wall -O2 -s -o mister_viz_server mister_viz_server.c `pkg-config --cflags --libs libudev`

/* mister_viz_server
 * A standalone implementation of the mister_viz protocol for Linux systems,
 * written in C.
 *
 * Works well on the Steam Deck, which is the intended use case.
 *
 * Socket bind address and port are hardcoded.
 *
 * Any input devices that have EVIOCGRAB called on them will not be captured.
 *
 */

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

typedef struct deviceinfo_t {
	char *name;
	uint8_t type;
	uint16_t vendor_id;
	uint16_t product_id;
} deviceinfo_t;

typedef struct state_t {
	nfds_t len;
	struct udev *udev_context;
	struct udev_monitor *monitor;
	struct pollfd *pool;
	struct deviceinfo_t *info;
} state_t;

state_t *state_create(void) {
	state_t *ret = (state_t *) malloc(sizeof(state_t));
	ret->len = 0;
	ret->pool = NULL;
	ret->info = NULL;
	return ret;
}

void state_destroy(state_t *state) {
	nfds_t i;
	if (state->pool != NULL) {
		for (i = 0; i < state->len; i++) {
			if (state->pool[i].fd >= 0) {
				close(state->pool[i].fd);
			}
		}
		free(state->pool);
	}
	if (state->info != NULL) {
		for (i = 0; i < state->len; i++) {
			if (state->info[i].name != NULL) {
				free(state->info[i].name);
			}
		}
		free(state->info);
	}
	free(state);
}

nfds_t state_add(state_t *state) {
	/* Adds a new blank entry into the state struct. */
	/* Returns the index number for the new entry. */
	nfds_t idx = state->len;
	state->pool = (struct pollfd *) realloc(state->pool, sizeof(struct pollfd) * (state->len + 1));
	state->info = (deviceinfo_t *) realloc(state->info, sizeof(deviceinfo_t) * (state->len + 1));
	state->len++;

	state->pool[idx].fd = -1;
	state->pool[idx].events = 0;
	state->pool[idx].revents = 0;
	state->info[idx].name = NULL;
	state->info[idx].type = FD_TYPE_UNDEFINED;
	//struct pollfd *ret = (&(state->pool))[state->len - 1];
	//memset(ret, -1, sizeof(struct pollfd));
	//deviceinfo_t *info = state->info[state->len - 1];
	//info->name = NULL;
	//memset(state->pool[state->len - 1], 0, sizeof(struct pollfd));

	//struct pollfd *ret = state->pool[state->len - 1];
	return idx;
}

void state_remove(state_t *state, nfds_t idx) {
	/* Removes entry at index `idx` from the state struct. */
	/* Items occurring past this entry will be moved to fill in the gap. */
	if (state->pool[idx].fd >= 0) {
		//printf("closing fd %d\n", state->pool[idx].fd);
		close(state->pool[idx].fd);
	}
	if (state->info[idx].name != NULL) {
		free(state->info[idx].name);
	}
	for (nfds_t i = idx; i < (state->len - 1); i++) {
		//printf("shuffling idx %ld to %ld\n", i+1, i);
		memcpy(&(state->pool[i]), &(state->pool[i+1]), sizeof(struct pollfd));
		memcpy(&(state->info[i]), &(state->info[i+1]), sizeof(deviceinfo_t));
	}
	state->len--;
	//printf("Realloccing state to size %ld\n", sizeof(struct pollfd *) * state->len);
	state->pool = (struct pollfd *) realloc(state->pool, sizeof(struct pollfd) * state->len);
	//printf("Reallocing info to size %ld\n", sizeof(deviceinfo_t) * state->len);
	state->info = (deviceinfo_t *) realloc(state->info, sizeof(deviceinfo_t) * state->len);
}

void state_print(state_t *state) {
	printf("Poll state contains %ld items:\n", state->len);
	for (nfds_t i = 0; i < state->len; i++) {
		//struct pollfd *p = (&(state->pool))[i];
		printf("  item %ld:\n", i);
		printf("    fd: %d\n", state->pool[i].fd);
		printf("    name: %s\n", state->info[i].name);
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

void input_socket_send(state_t *state, uint16_t vid, uint16_t pid, struct input_event *ev) {
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

	for (nfds_t i = 0; i < state->len; i++) {
		if (state->info[i].type == FD_TYPE_CLIENTSOCKET) {
			if (write(state->pool[i].fd, (char *) &packet, sizeof(packet)) != sizeof(packet)) {
				printf("WARNING: input_socket_send failed to write all data!\n");
			}
		}
	}
}

void handle_udev_device(state_t *state, struct udev_device *udevice) {
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


				nfds_t idx = state_add(state);
				struct pollfd *pollslot = &(state->pool[idx]);
				deviceinfo_t *infoslot  = &(state->info[idx]);

				//printf("Pollslot fd: %d\n", pollslot->fd);
				//printf("Pollslot fd: %d\n", state->pool[idx].fd);
				pollslot->fd = fd;
				pollslot->events = POLLIN;
				//printf("Pollslot fd: %d\n", pollslot->fd);
				//printf("Pollslot fd: %d\n", state->pool[idx].fd);
				infoslot->vendor_id = vid;
				infoslot->product_id = pid;

				char devname_temp[255];
				if (ioctl(fd, EVIOCGNAME(255 - 1), &devname_temp) < 1) {
					devname_temp[0] = '\0';
				}
				infoslot->name = strdup(devname_temp);
				//printf("device name: %s\n", infoslot->name);
				//printf("device name strlen: %ld\n", strlen(infoslot->name));
				//printf("device name: %s\n", state->info[idx].name);
				printf("Adding input device: %s\n", state->info[idx].name);

				infoslot->type = FD_TYPE_INPUT;
				
				//close(fd);
				//state_print(state);

			}
		}

		//const char *driver = udev_device_get_driver(udevice);
		//printf("driver: %s\n", driver);

		//const char *sysname = udev_device_get_sysname(udevice);
		//printf("sysname: %s\n", sysname);


	}
	//printf("\n");
}

void check_input(state_t *state) {
	int return_value = poll(state->pool, state->len, -1);
	//printf("poll return value: %d\n", return_value);
	if (return_value > 0) {
		for (nfds_t i = 0; i < state->len; i++) {
			//printf("slot %ld type %d revents %d\n", i, state->info[i].type, state->pool[i].revents);
			switch(state->info[i].type) {
				case FD_TYPE_UDEV:
					if (state->pool[i].revents > 0) {
						//printf("Udev has something to say! revents: %d\n", state->pool[i].revents);
					}
					if (state->pool[i].revents & POLLIN) {
						state->pool[i].revents &= ~POLLIN;
						struct udev_device *udevice = udev_monitor_receive_device(state->monitor);
						if (udevice) {
							if (strcmp(udev_device_get_action(udevice), "add") == 0) {
								handle_udev_device(state, udevice);
							}
							//printf("  action: %s, devnode: %s, subsystem: %s\n", udev_device_get_action(udevice), udev_device_get_devnode(udevice), udev_device_get_subsystem(udevice));
							udev_device_unref(udevice);
						}
					}
					break;
				case FD_TYPE_INPUT:
					bool do_print = false;
					if (state->pool[i].revents > 0) {
						do_print = true;
					}
					if (do_print) {
						//printf("Device %ld (%s) revents: %d\n", i, state->info[i].name, state->pool[i].revents);
					}
					if (state->pool[i].revents & POLLIN) {
						//printf("  POLLIN\n");
						state->pool[i].revents &= ~POLLIN;
						struct input_event ev;
						memset(&ev, 0, sizeof(ev));
						if (read(state->pool[i].fd, &ev, sizeof(ev)) == sizeof(ev)) {
							//printf("  %ld.%06ld: read event!\n", ev.time.tv_sec, ev.time.tv_usec);
							input_socket_send(state, state->info[i].vendor_id, state->info[i].product_id, &ev);
						}
					}
					if (state->pool[i].revents > 0) {
						printf("  UNKNOWN EVENT (revents: %d)\n", state->pool[i].revents);
					}
					if (state->pool[i].revents & POLLHUP) {
						printf("  POLLHUP\n");
						state_remove(state, i);
						i--;  // careful, modifying i here!
					}
					break;
				case FD_TYPE_LISTENSOCKET:
					if (state->pool[i].revents & POLLIN) {
						state->pool[i].revents &= ~POLLIN;
						//printf("Accepting socket\n");
						int client = accept(state->pool[i].fd, NULL, NULL);
						nfds_t idx = state_add(state);
						state->pool[idx].fd = client;
						state->pool[idx].events = POLLIN;
						state->info[idx].type = FD_TYPE_CLIENTSOCKET;
						/* Get the remote peer address */
						struct sockaddr_in remote_addr;
						socklen_t addr_len = sizeof(remote_addr);
						if (getpeername(state->pool[idx].fd, (struct sockaddr *)&remote_addr, &addr_len) == 0) {
							char ip_str[INET_ADDRSTRLEN];
							inet_ntop(AF_INET, &(remote_addr.sin_addr), ip_str, INET_ADDRSTRLEN);
							//printf("Remote IP: %s, Port: %d\n", ip_str, ntohs(remote_addr.sin_port));
							char remote_peer_str[256];
							snprintf(remote_peer_str, 255, "%s:%d", ip_str, ntohs(remote_addr.sin_port));
							state->info[idx].name = strdup(remote_peer_str);
						} else {
							//printf("Getpeername failed\n");
							state->info[idx].name = strdup("client socket");
						}
						printf("Connected: %s\n", state->info[idx].name);

					}
					if (state->pool[i].revents > 0) {
						printf("Unhandled revents for listen socket: %d\n", state->pool[i].revents);
					}
					break;
				case FD_TYPE_CLIENTSOCKET:
					bool do_close = false;
					if (state->pool[i].revents & POLLIN) {
						state->pool[i].revents &= ~POLLIN;
						char trash[1];
						int rlen = read(state->pool[i].fd, trash, 1);
						if (rlen == 0) {
							do_close = true;
						} else {
							uint8_t opcode = trash[0];
							if (opcode == OP_PING) {
								trash[0] = OP_PONG;
								if (write(state->pool[i].fd, (char *) trash, 1) != 1) {
									printf("WARNING: failed to send PING response!\n");
								}
							} else {
								printf("Unknown opcode %d from %s, dropping client\n", opcode, state->info[i].name);
								do_close = true;
							}
						}
					}
					if (state->pool[i].revents & (POLLERR | POLLHUP | POLLNVAL)) {
						do_close = true;
						state->pool[i].revents &= ~(POLLERR | POLLHUP | POLLNVAL);
					}
					if (state->pool[i].revents > 0) {
						printf("Unhandled events for client %s: %d\n", state->info[i].name, state->pool[i].revents);
					}
					if (do_close) {
						printf("closing client %s\n", state->info[i].name);
						shutdown(state->pool[i].fd, SHUT_RDWR);
						state_remove(state, i);
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
	state_t *state = state_create();
	state->udev_context = udev_new();

	struct udev_enumerate *enumerator = udev_enumerate_new(state->udev_context);

	udev_enumerate_add_match_subsystem(enumerator, "input");
	//int result = udev_enumerate_scan_devices(enumerator);
	udev_enumerate_scan_devices(enumerator);
	//fprintf(stderr, "udev_enumerate_scan_devices() result: %d\n", result);



	nfds_t udev_idx = state_add(state);
	//printf("Using idx %ld for udev\n", udev_idx);
	state->info[udev_idx].name = strdup("udev monitor");
	state->info[udev_idx].type = FD_TYPE_UDEV;

	//state_print(state);

	struct udev_list_entry *udev_entry = udev_enumerate_get_list_entry(enumerator);
	while (udev_entry != NULL) {
		const char *syspath = udev_list_entry_get_name(udev_entry);
		struct udev_device *udevice = udev_device_new_from_syspath(state->udev_context, syspath);
		//printf("%s\n", syspath);
		handle_udev_device(state, udevice);
		udev_device_unref(udevice);
		udev_entry = udev_list_entry_get_next(udev_entry);
	}

	udev_enumerate_unref(enumerator);

	state->monitor = udev_monitor_new_from_netlink(state->udev_context, "udev");
	if (!state->monitor) {
		fprintf(stderr, "Failed to create udev monitor!\n");
		return EXIT_FAILURE;
	}
	if (udev_monitor_filter_add_match_subsystem_devtype(state->monitor, "input", NULL) < 0) {
		fprintf(stderr, "Failed to add subsystem filter to udev monitor!\n");
		return EXIT_FAILURE;
	}
	if (udev_monitor_enable_receiving(state->monitor) < 0) {
		fprintf(stderr, "Failed to enable receiving on udev monitor!\n");
		return EXIT_FAILURE;
	}

	state->pool[udev_idx].fd = udev_monitor_get_fd(state->monitor);
	state->pool[udev_idx].events = POLLIN;

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
	nfds_t listensock_idx = state_add(state);
	printf("Using idx %ld for listen socket\n", listensock_idx);
	state->pool[listensock_idx].fd   = sock;
	state->pool[listensock_idx].events = POLLIN;
	state->info[listensock_idx].name = strdup("listen socket");
	state->info[listensock_idx].type = FD_TYPE_LISTENSOCKET;

	printf("Listening on port %d\n", port);
	printf("  sizeof struct timeval: %ld\n", sizeof(struct timeval));
	printf("  sizeof struct input_event: %ld\n", sizeof(struct input_event));
	printf("  sizeof struct input_socket_packet: %ld\n", sizeof(struct input_socket_packet));

	while (true) {
		check_input(state);
	}


	udev_unref(state->udev_context);

	state_destroy(state);
	return 0;
}
