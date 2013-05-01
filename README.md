# Tunnels

`tunnels` allows you to set system-wide, transparent proxying rules on a per-domain-name basis.

For example...

* You can redirect all traffic to `*.intranet` to go over an [SSH] tunnel which can reach your intranet.
* You can redirect all traffic to `slow-image-site.com` to go through [Squid] or other caching proxy.
* You can transparently redirect all `*.onion` traffic over [Tor]'s SOCKS proxy.
* You can block all traffic to `*.random-ad-company.com`.

## How it works

`tunnels` is a set of components that interact together:

* It has a DNS server which sits in front of your favorite DNS server. It will return a fake IP address when queried about one of the domains you have defined some proxying rules for.
* The system's IP routing table is modified such that the fake IP address that was returned is now routed to the local machine.
* One or more sockets are opened, listening for connections to the fake IP address that was returned.
* Any connection received will go over the proxy specified for the particular domain that was queried in the first place. The DNS resolution of the actual domain name will be done **on the remote side**.
* If the DNS server is queried about a domain you haven't specified rules for, it will either forward the query to your preferred upstream DNS server and return the result without modification, or it can completely block the connection.

## Privacy notice

Do **NOT** rely on this utility *alone* to protect your privacy or anonymity. This is especially important if you plan on using this for browsing the Web. Indeed, HTML allows web pages to request resources hosted on other domains than the website's own domain. In turn, those resources may load other resources from other domains, and so on. If you only define rules for the website's main domain, all of the other requests will **not** respect these rules.

To avoid this, I recommend using a browser extension such as [RequestPolicy]. It lets you build a whitelist describing which domains can load resources from which other domains, and blocks all other cross-domain requests by default.

Alternatively, you can set `blockUndefinedDomains` to `true` in the configuration, which will cause all connections to domains you have not specified rules for to fail. Be careful, however, that the application in question doesn't fall back to directly connecting to an IP address, perhaps stored as part of its code.

This application also doesn't protect you against anything that ignores `/etc/resolv.conf` or otherwise makes its own DNS lookups, and the above suggestions will not help. Such applications tend to be malicious and should be run in isolated environments anyway.

## Usage

	tunnels <configuration directory>

The provided configuration directory should contain one or more YAML configuration files of the following form: (TODO)

[SSH]: https://en.wikipedia.org/wiki/Secure_Shell
[Squid]: http://www.squid-cache.org/
[Tor]: https://www.torproject.org/
[RequestPolicy]: https://www.requestpolicy.com/
