# FTP Reference

## When To Use

Use FTP only for legacy servers that do not offer SSH-based transfer methods.
Prefer SFTP or FTPS if they are available.

## Common Patterns

### Interactive FTP

```bash
ftp ftp.example.com
```

Typical session:

```text
user USERNAME
put local-file.txt
get remote-file.txt
bye
```

### Scripted FTP With `lftp`

```bash
lftp -u USERNAME,PASSWORD ftp://ftp.example.com <<'EOF'
put local-file.txt
get remote-file.txt
bye
EOF
```

## Guidance

- Use FTP for non-sensitive artifacts when the server leaves no better option.
- Avoid plaintext FTP for secrets, tokens, or private agent logs.
- Prefer batch uploads and downloads over interactive manual edits.
- Keep FTP as an artifact transport only; tmux control should stay on SSH or
  local commands.
