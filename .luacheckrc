std = "lua54"

-- Disable overly strict line-length rule for configs
max_line_length = false

-- Per-file configuration
files = {
  ["files/nvim.init.lua"] = {
    globals = { "vim" },
  },
  ["files/imapfilter.config.lua"] = {
    read_globals = { "IMAP" },
    globals = { "options", "gmail", "thinkspan", "accounts", "messages", "mailboxes", "folders" },
  },
}
