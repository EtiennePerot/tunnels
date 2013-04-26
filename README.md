# Tunnels

`tunnels` allows you to set system-wide, transparent proxying rules on a per-domain-name basis.

For example...

* You can redirect all traffic to `*.intranet` to go over an SSH tunnel which can reach your intranet.
* You can redirect all traffic to `slow-image-site.com` to go through Squid or other caching proxy.
* You can transparently redirect all `*.onion` traffic over Tor's SOCKS proxy.
* You can block all traffic to `*.random-ad-company.com`.

## How it works

`tunnels` is a set of components that interact together:

* It has a DNS server which sits in front of your favorite DNS server. It will return a fake IP address when queried about one of the domains you have defined some proxying rules for.
* The system's IP routing table is modified such that the fake IP address that was returned is now routed to the local machine.
* One or more sockets are opened, listening for connections to the fake IP address that was returned.
* Any connection received will go over the proxy specified for the particular domain that was queried in the first place.
* If the DNS server is queried about a domain you do not have rules for, it will forward the query to your preferred upstream DNS server and return the result without modification.

## Usage

	tunnels <configuration directory>

The provided configuration directory should contain one or more YAML configuration files of the following form: (TODO)
