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

	tunnels <conf1> [<conf2> [<conf3> [...]]]

Each configuration entry (`<confN>`) can either be a file or a directory. Directories will be searched recursively and their contents will be treated as configuration files.

Each configuration file is of the following form:

```yaml
proxies:
        mysocksproxy:
                type: socks5
                address: myhost.com
                port: 8072
        tor:
                type: socks5
                address: 127.0.0.1
                port: 9050
        myvps:
                type: ssh
                address: mybox.randomvpsprovider.com
                username: bob
                privateKey: /home/bob/.ssh/id_rsa
                rsaFingerprint: 01:23:45:97:89:ab:cd:ef:01:23:45:97:89:ab:cd:ef
                ecdsaFingerprint: fe:dc:ba:98:76:54:32:10:fe:dc:ba:98:76:54:32:10

ports:
        dns: u53
        ssh: t22
        http: t80
        https: t443
        web: http + https

rules:
        .google.*@web: mysocksproxy
        .example.org@web, .example.com@web: mysocksproxy
        vps-ip.pls@https:
                proxy: myvps
                forcedAddress: icanhazip.com
        .duckduckgo.com@web:
                proxy: tor
                forcedAddress: duckduckgo.com, 3g2upl4pq6kufc4m.onion
        *.onion@web+ssh: tor
        mysecondvps.randomvpsprovider.com@ssh: myvps

upstreamDns: 127.0.0.1:5353, 94.75.228.29, 87.118.100.175, 213.73.91.35
blockUndefinedDomains: false
```

Every configuration file may have main configuration options (such as `upstreamDns` and `blockUndefinedDomains` in the example above), though only one may contain a value for a specific option (you can't have two files specifying the value of the `blockUndefinedDomains` option).

Three sections, however, may appear in as many configuration files as required: `proxies`, `ports`, and `rules`. The final set of proxies, ports, and rules is the result of merging all these sections from all configuration files.

### `proxies` section

Each entry in the `proxies` section is the name of a proxy. Each entry contains the option `type`, which specifies the type of proxy being defined. These correspond by name to files in `src/proxies/<proxy type>.py`. Other configuration options depend on the proxy type being used.

Currently, `tunnels` supports 3 types of proxy:

* `socks5`: A SOCKSv5 server. UDP support is currently not implemented, thus this is mostly equivalent to SOCKSv4a right now. Regardless, this proxy type allows you to connect to a SOCKSv5 proxy at some arbitrary address. Configuration options:
    * `address`: The domain name or IP address of the SOCKSv5 server. If you use a domain name, make sure your configuration allows you to resolve it once `tunnels` is running!
    * `port`: The number of the TCP port the SOCKSv5 server is listening on. Default: `1080`
    * `username`: *Not implemented*
    * `password`: *Not implemented*
* `http`: An HTTP proxy server (not HTTPS!). Only supports TCP proxying because that's how HTTP proxies work. The configuration options are the same as `socks5`, except the default port number is `80`.
* `ssh`: An SSH tunnel. Only supports TCP, but could be expanded to transport UDP packets over the TCP link (patches welcome), but this would be pretty slow. Configuration options:
    * `address`: The domain name or IP address of the SSH server. SSH aliases will not work. If you use a domain name, make sure your configuration allows you to resolve it once `tunnels` is running!
    * `port`: The TCP port the SSH server is listening on. Default: `22`
    * `username`: The username to log in as. Because of limitations in [Paramiko], the library used for communicating with the server, this user has to be able to spawn a shell with the `echo` command available. `tunnels` uses this to check whether the connection is still alive or not. This user also need to open TCP/IP tunnels.
    * `privateKey`: Full path to your SSH private key used to log in to the server. Make sure to include the full path. `~` will not point to where you might expect, because `tunnels` runs as root. The key may either be an RSA key or an ECDSA key (if your [Paramiko] library supports it).
    * `rsaFingerprint`: Fingerprint of the server's RSA key. If not provided and the server presents its RSA key, the connection will be closed.
    * `ecdsaFingerprint`: Fingerprint of the server's ECDSA key. Only useful if your [Paramiko] library supports ECDSA. If not provided and the server presents its ECDSA key, the connection will be closed.

### `ports` section

Each entry in the `ports` is a human-readable aliases for a certain port or set of ports. It is associated with a `+`-separated string of raw port numbers, or other port aliases.

Raw port numbers are of the form `tNNNN` for TCP ports, and `uNNNN` for UDP ports.

Aliases are global across all configuration files. You usually do not have to write `ports` sections yourself; the default set provided at `conf.d.sample/basic-ports.yml` should cover most use-cases.

### `rules` section

Each entry in the `rules` section is of the following general form:

```yaml
domain-pattern-1@port1+port2+..., domain-pattern-2@port3+port4+..., ...:
    proxy: proxy-name
    forcedAddress: forcedAddress1, forcedAddress2, ...
```

* Each `domain-pattern` is as you would expect. You can use a full domain name (`mydomain.com`), you can use wildcards to match a domain part (`*.mydomain.com`, `*.mydomain.*`). You can also use the form `.mydomain.com` as an alias for `mydomain.com, *.mydomain.com`. *Implementation detail*: Wilcard matches of the form `*.the.rest.is.fixed` are efficient; other forms of wildcard matches are not and will slow down lookup. Avoid them if possible.
* Each `domain-pattern` is followed by a `+`-separated list of port aliases or raw port numbers. The syntax is the same as the one described in the `ports` section.
* `proxy` is the name of the proxy to use for this rule.
* `forcedAddress` is a comma-separated list of domain names or IP addresses. When a request for one of the domains matching the defined patterns is made, the specified proxy will actually be asked to contact one of the domain names or IPs provided in `forcedAddress` (randomly, if there are more than one of them). This is useful to create domain aliases for your own use (for example, `ip.pls` to `icanhazip.com`), or to spread load across many servers.

When `forcedAddress` is not necessary, the entire rule can be written as one line:

```yaml
domain-pattern-1@port1+port2+..., domain-pattern-2@port3+port4+..., ...: proxy-name
```

Thus, most of the time, you'll just be writing something like this:

```yaml
.mydomain.com@web: myproxy
```

### Main configuration options

The following options must be specified at the root level of configuration files. All options are optional unless otherwise noted.

* `upstreamDns`: **Required**: A comma-separated list of `ipAddress:portNumber` corresponding to DNS servers that should be queried when needed. If `portNumber` is not provided, it is assumed to be `53`. Whenever `tunnels` needs to perform a real DNS query, it will contact one of these DNS servers at random.
* `privateAddresses`: An IP subnet to reserve for `tunnels` use. This subnet will be locally routed when starting `tunnels`. The default is `10.42.0.0/16`, but you may want to use something like `127.42.0.0/16` for peace of mind. Do **not** use `127.0.0.1/24`, as that may break some other applications. Larger subnets mean being able to hold more IP-domain associations at once.
* `blockUndefinedDomains`: When queried about a domain name for which no rules exist, `tunnels` can either ask one of the upstream DNS server about it and return its reply (set this to `true`) or can return a locally-routed address to which all connections will fail (set this to `false`). The default is `true` (ask upstream and reply truthfully).
* `silentLog`: A comma-separated list of modules to hide from the debugging output. Module names are written in `[brackets]` in the debugging output. For example, to silence all `[DNS]` and `[SRV]` messages, use `DNS, SRV`. The default value is the empty string (i.e. don't hide anything).
* `addressCleanupTime`: When a domain name has been associated to a fake IP address, this association will only last for some time. The TTL in the request packet is set to a fourth of the value of `addressCleanupTime`, so that applications forget about the association quickly enough. After `addressCleanupTime` seconds since the last DNS query, `tunnels` itself forgets the association, and the IP becomes free to use for some other domain. By default, associations last an hour. Increasing this value means you can cycle through IPs more quickly, but means more load on `tunnels`'s pseudo-DNS server.
* `dnsBindAddress`: The address used for `tunnels`'s pseudo-DNS server to bind to. Binds to `127.0.0.1` by default.
* `dnsPort`: The UDP port number used for `tunnels`'s pseudo-DNS server to bind to. The default value is `53`. Changing this will break your DNS unless you have another DNS server listening on port 53 (and eventually forwarding some DNS request to `tunnels`).
* `overwriteResolvconf`: Whether to overwrite the system's `resolv.conf` file on startup and point it to `dnsBindAddress`. The default is `true`. Your old `resolv.conf` file will be backed up.
* `restoreResolvConf`: Whether to restore the system's `resolv.conf` file from backup on exit. The default is `true`. This only makes sense if `overwriteResolvconf` is true as well.
* `makeResolvconfImmutable`: Whether to run `chattr +i /path/to/resolv.conf` after having overwritten it. The default is `true`. This only makes sense if `overwriteResolvconf` is true as well.
* `resolvconfPath`: The path to your system's `resolv.conf` file. The default is `/etc/resolv.conf`.
* `resolvconfBackupPath`: The path to store the backup for the old `resolv.conf` file. The default is `/etc/resolv.conf.tunnels-backup`. This only matters if `overwriteResolvconf` is true.
* `dnsPacketSize`: How large can a single DNS packet be. The default is `65535`. You should never need to change this.
* `upstreamDnsTimeout`: How long to wait for a reply from an upstream DNS server after having sent a query. The default is `300` (seconds).
* `temporaryBindPortRange`: A port range which `tunnels` may use to bind its temporary sockets to. `iptables` rules are used to redirect connections to these ports. The default is `30000-55000`. Note that you can still use any port in this range for some other purposes; `tunnels` will jsut keep trying random ports in this range until it succeeds. A larger range means more concurrent connections.
* `iptablesChain`: The name of the `iptables` chain to store all redirection rules into. The default is `tunnels_redirects`. You should never need to change this unless you have a really weird `iptables` setup.

[SSH]: https://en.wikipedia.org/wiki/Secure_Shell
[Squid]: http://www.squid-cache.org/
[Tor]: https://www.torproject.org/
[RequestPolicy]: https://www.requestpolicy.com/
[Paramiko]: https://github.com/paramiko/paramiko
