"Dan Sullivan
"~/.vimrc

:set number
:set ruler
:set ignorecase
:syntax on
":10 sp

"smart indent for python
":help smartindent
":help auto-setting embed in source for portability
:set smartindent
:set tabstop=4
:set shiftwidth=4
:set expandtab
:set list

"color scheme
:set background=dark
:hi clear
if exists("syntax_on")
      syntax reset
      endif
"term = underline can be added to to any color setting to underline something
:hi Normal ctermfg=White guifg=White guibg=#35536f
:hi LineNr ctermfg=White guifg=#d700ff

"disable visual bell
:set novisualbell

"http://got-ravings.blogspot.com/2008/08/vim-pr0n-making-statuslines-that-own.html
:set laststatus=2
:set statusline= 
:set statusline+=--[%F]-
:set statusline+=[%c,%l/%L]-
:set statusline+=[%{strlen(&fenc)?&fenc:'none'}]-
:set statusline+=[%{FileSize()}]-
":set statusline+=[%03.b]
:set statusline+=[%03.b]-
"Set the color, for some reason these seem transposed.
:set statusline+=[%P] 
:hi StatusLine ctermbg=white ctermfg=black

function! FileSize()
    let bytes = getfsize(expand("%:p"))
    if bytes <= 0
        return ""
    endif
    if bytes < 1024
        return bytes
    else
        return (bytes / 1024) . "K"
     endif
endfunction
