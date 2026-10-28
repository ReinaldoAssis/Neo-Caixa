# Auto-updater — falha de certificado TLS (app empacotado)

Data: 2026-10-28 · Branch: `master`

## Sintoma

No app compilado, a checagem/baixa de atualizacao no GitHub falha com algo
proximo de `CERTIFICATE_VERIFY_FAILED` / "certificado invalido".

## Causa

`app/core/updater.py` usava `ssl.create_default_context()` sem `cafile`.
Num app PyInstaller, o `ssl` procura o bundle de CAs no prefixo do Python que
compilou o executavel (ex.: `/Users/runner/...`, `/opt/hostedtoolcache/...`).
Esse caminho nao existe na maquina do usuario, entao a cadeia do GitHub nao
tem raiz de confianca e a verificacao TLS falha.

No build de desenvolvimento funciona porque o Python instalado tem o bundle
no prefixo real (`ssl.get_default_verify_paths().cafile`).

## Correcao

- `_ca_bundle()`: prioriza `certifi.where()` (bundle embarcado pelo
  PyInstaller), depois `SSL_CERT_FILE` se existir, depois bundles do SO
  (`/etc/ssl/cert.pem`, `/etc/ssl/certs/ca-certificates.crt`,
  `/etc/pki/tls/certs/ca-bundle.crt`).
- `_ssl_context()`: `create_default_context(cafile=bundle)`. Removido o
  fallback antigo que desligava a verificacao (`CERT_NONE`) — baixar um
  executavel sem verificar TLS nao e aceitavel.
- `requirements.txt` e `helena.spec`: `certifi` como dependencia e
  `collect_data_files('certifi')` nos `datas` do build.
- `mensagem_erro()`: erro de certificado vira texto acionavel (atualizar
  manualmente pela pagina de releases) e nao um stack trace cru.
- `check_for_update`: loga `versao`, `frozen` e caminho de CA para diagnostico
  no `app.log`; usa `logger.exception`.
- `/api/update/download` devolve `mensagem_erro(exc)`.

## Verificacao

- `_ca_bundle()` -> `certifi/cacert.pem` no venv; sem certifi (simulado) ->
  `/etc/ssl/cert.pem`.
- `_ssl_context()` carrega 128 CAs e abre `api.github.com` com HTTP 200.
- `collect_data_files('certifi')` inclui `cacert.pem` no build.
- Testes em `tests/test_updater_version.py` (bundle, contexto, mensagem e
  `check_for_update` com `URLError` de certificado).

## Observacao operacional

O app instalado hoje (1.0.20/1.0.21 ou anterior) ainda tem o updater antigo.
A correcao vale a partir do primeiro build novo instalado manualmente; depois
disso o auto-update passa a funcionar.
