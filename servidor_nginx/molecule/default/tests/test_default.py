def test_nginx_instalado_e_rodando(host):
    # 1. Verifica se o pacote 'nginx' foi instalado no sistema
    pacote_nginx = host.package("nginx")
    assert pacote_nginx.is_installed

    # 2. Verifica se o servico do Nginx esta ativo e habilitado no boot
    servico_nginx = host.service("nginx")
    assert servico_nginx.is_running
    assert servico_nginx.is_enabled

    # 3. Verifica se o servidor esta escutando na porta 80 (HTTP)
    porta_web = host.socket("tcp://0.0.0.0:80")
    assert porta_web.is_listening
