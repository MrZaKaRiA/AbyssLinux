" Compile TeX with SyncTeX and Vim's quickfix list.
setlocal makeprg=latexmk\ -pdf\ -interaction=nonstopmode\ -file-line-error\ -synctex=1\ %
setlocal errorformat=%f:%l:\ %m,%f:%l:%m,%-G%.%#
nnoremap <buffer> <localleader>m :make<CR>
command! -buffer TexView call system('zathura --synctex-forward ' . shellescape(line('.') . ':1:' . expand('%:p')) . ' ' . shellescape(expand('%:p:r') . '.pdf') . ' >/dev/null 2>&1 &')
