std = "lua54"

-- Disable overly strict line-length rule for configs
max_line_length = false

-- Per-file configuration
files = {
  ["files/nvim.init.lua"] = {
    read_globals = { "vim" },
    globals = { "vim" },
    ignore = { "122" }, -- Ignore setting read-only field
  },
  ["files/imapfilter.config.lua"] = {
    read_globals = { "IMAP", "options" },
    globals = { "gmail", "thinkspan", "accounts", "messages", "mailboxes", "folders" },
    ignore = { "122" }, -- Ignore setting read-only field
  },
}
