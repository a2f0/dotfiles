options.timeout = 1200
options.create = true
options.subscribe = true
options.expunge = true

gmail = IMAP {
    server = "imap.gmail.com",
    username = "dansullivan@gmail.com",
    password = os.getenv("GMAIL_APP_SPECIFIC_PASSWORD"),
    ssl = "tls1"
}

senders = {
    "spammer@spammerdomain.com", "youtube.com", "Mailer Delivery System"
}

for sender = 1, #senders do
    print("Removing messages from " .. senders[sender])
    -- messages = gmail["[Gmail]/All Mail"]:contain_from(senders[sender])
    -- messages:move_messages(account1["[Gmail]/Trash"])
end
