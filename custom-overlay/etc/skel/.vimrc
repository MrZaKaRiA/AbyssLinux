" ~/.vimrc - Abyss Linux defaults (vim is $EDITOR when VS Code is not installed)

unlet! skip_defaults_vim
source $VIMRUNTIME/defaults.vim

set number
set expandtab shiftwidth=4 tabstop=4 softtabstop=4 smartindent
set ignorecase smartcase hlsearch incsearch
set mouse=a
set laststatus=2
set splitbelow splitright
set encoding=utf-8

if has('clipboard_working')
    set clipboard=unnamedplus
endif

" Persistent undo
if has('persistent_undo')
    let s:undo = expand('~/.vim/undo')
    if !isdirectory(s:undo)
        call mkdir(s:undo, 'p', 0700)
    endif
    let &undodir = s:undo
    set undofile
endif

" Dark theme on the terminal's own background
if has('termguicolors') && $TERM =~# 'st\|xterm\|alacritty'
    set termguicolors
endif
set background=dark
silent! colorscheme habamax
highlight Normal ctermbg=NONE guibg=NONE
highlight LineNr guifg=#6d5a99 ctermfg=97
highlight CursorLineNr guifg=#a855f7 ctermfg=135
