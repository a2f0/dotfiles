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

mailboxes, folders = gmail:list_all('*')
print("=== mailboxes")
for _, m in ipairs(mailboxes) do print(m) end
print("=== folders")
for _, f in ipairs(folders) do print(f) end

-- Cleanup GitHub
messages = gmail["INBOX"]:contain_from("notifications@github.com")
messages:move_messages(gmail["Keep/GitHub"])
messages = gmail["Keep/GitHub"]:is_older(30)
messages:move_messages(gmail['[Gmail]/Trash'])

-- Cleanup Sent
messages = gmail["[Gmail]/Sent Mail"]:is_older(1095)
messages:move_messages(gmail['[Gmail]/Trash'])

-- Cleanup Spam Folder
senders = {
    "americastestkitchen.com",
    "marcusmillichap.com"
}
for sender = 1, #senders do
    print("Removing messages from " .. senders[sender])
    messages = gmail["Junk"]:contain_from(senders[sender])

    -- messages:move_messages(account1["[Gmail]/Trash"])
end
