-- disable builtin file browser
vim.g.loaded_netrw = 1
vim.g.loaded_netrwPlugin = 1

-- set termguicolors to enable highlight groups
vim.opt.termguicolors = true

vim.opt.wildmode = "longest:full,full"
vim.opt.wildmenu = true

vim.opt.number = true
vim.opt.wrap = true

vim.cmd([[ let g:neo_tree_remove_legacy_commands = 1 ]])

local ensure_packer = function()
  local fn = vim.fn
  local install_path = fn.stdpath('data')..'/site/pack/packer/start/packer.nvim'
  if fn.empty(fn.glob(install_path)) > 0 then
    fn.system({'git', 'clone', '--depth', '1', 'https://github.com/wbthomason/packer.nvim', install_path})
    vim.cmd [[packadd packer.nvim]]
    return true
  end
  return false
end

local packer_bootstrap = ensure_packer()

return require('packer').startup(function(use)
  use 'wbthomason/packer.nvim'
  use {
    "nvim-neo-tree/neo-tree.nvim",
      branch = "v2.x",
      requires = {
        "nvim-lua/plenary.nvim",
        "nvim-tree/nvim-web-devicons", -- not strictly required, but recommended
        "MunifTanjim/nui.nvim",
      }
  }
  use {
    'nvim-telescope/telescope.nvim', tag = '0.1.2',
     requires = { {'nvim-lua/plenary.nvim'} }
  }
  require('telescope').setup{
    defaults = {
      file_ignore_patterns = {
        "node_modules"
      }
    }
  }
  if packer_bootstrap then
    require('packer').sync()
  end
end)