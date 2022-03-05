options.timeout = 1200
options.create = true
options.subscribe = true
options.expunge = true

account1 = IMAP {
    server = "imap.gmail.com",
    username = "dansullivan@gmail.com",
    ssl = "tls1"
}
