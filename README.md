# O Ciclo de Vida da Infraestrutura como Código (IaC): Automação e Testes com Ansible, Molecule e Testinfra

**Autor:** Vinícius Lacerda (`vlacerda93`)  
**Repositório do Projeto:** [github.com/vlacerda93/desafio-iac-ansible-molecule](https://github.com/vlacerda93/desafio-iac-ansible-molecule)

---

## Parte 1 — Relatório Teórico e Análise Crítica

### 1. Infraestrutura como Código (IaC) vs. Configuração Manual

Durante muito tempo, provisionar e manter servidores significava acessar cada máquina manualmente via SSH ou clicar em dezenas de menus em painéis de nuvem (*ClickOps*). Embora essa abordagem funcione quando temos apenas um servidor de testes, ela se torna insustentável em ambientes reais de operação por três motivos centrais: falta de escala, ausência de histórico confiável e o fenômeno dos *"servidores floco de neve"* (*snowflake servers*) — máquinas que, após meses de pequenos ajustes manuais não documentados, ficam diferentes umas das outras a ponto de ninguém saber exatamente como reproduzi-las do zero.

Quando tratamos a infraestrutura como código fonte (IaC) utilizando o **Ansible**, substituímos roteiros manuais por arquivos declarativos legíveis (`.yml`). Essa mudança traz ganhos diretos para a engenharia de operações:

- **Escalabilidade real:** O mesmo esforço necessário para escrever as tarefas de configuração de 1 servidor Ubuntu permite aplicar a mesma receita em 50 ou 500 servidores simultaneamente, sem risco de esquecer um parâmetro ou errar um comando por cansaço humano.
- **Versionamento com Git:** Assim como no desenvolvimento de software, toda a infraestrutura passa a morar em um repositório Git. Se uma atualização de configuração introduzir um comportamento inesperado, não precisamos adivinhar o que foi alterado: basta consultar o `git diff` e reverter para o commit anterior (`git revert`) em segundos.
- **Rastreabilidade e Auditoria:** Cada mudança no servidor deixa de ser uma ação invisível feita no terminal de madrugada e passa a ter autor, data, mensagem de commit e revisão por pares (*Pull Request*). A própria receita Ansible funciona como uma documentação viva da arquitetura.

---

### 2. O Conceito de Idempotência no Contexto do Ansible

Na matemática e na ciência da computação, uma operação **idempotente** é aquela que pode ser aplicada múltiplas vezes sem alterar o resultado além da aplicação inicial. Trazendo para o mundo do Ansible, idempotência significa que nós não escrevemos uma sequência cega de comandos imperativos (como `apt-get install nginx` jogado num script Bash comum), mas sim declaramos o **estado final desejado** do sistema operacional.

Se rodarmos um script Bash mal construído dez vezes seguidas para adicionar uma linha num arquivo de configuração ou iniciar um processo, corremos o risco de duplicar entradas dez vezes, reiniciar serviços que já estavam atendendo clientes ou gerar erros fatais porque a pasta ou porta já existe. No Ansible, módulos nativos como `ansible.builtin.apt` (com `state: present`) e `ansible.builtin.service` (com `state: started` e `enabled: yes`) primeiro **inspecionam o estado atual** do servidor antes de agir:

1. **Na 1ª execução:** O Ansible verifica que o pacote `nginx` não está instalado e que o serviço não existe. Ele executa a instalação, inicia o daemon e reporta `changed=2`.
2. **Da 2ª à 10ª execução consecutiva:** O Ansible consulta o banco de pacotes do Ubuntu e o `systemd`, constata que o pacote já está presente e que o serviço já está rodando e habilitado no boot, e simplesmente **não executa nenhuma alteração desnecessária**, encerrando com `changed=0` e `failed=0`.

Na prática do nosso laboratório no GitHub Codespaces, vimos isso acontecer ao vivo: enquanto a fase `converge` registrou `ok=4 changed=2`, a fase seguinte (`idempotence`) reexecutou exatamente o mesmo playbook e retornou `ok=4 changed=0`, provando que a automação é segura para ser reaplicada em produção a qualquer momento sem causar indisponibilidade.

---

### 3. Testes de Infraestrutura com Molecule e Testinfra

Escrever infraestrutura como código resolve o problema do trabalho manual, mas cria um novo risco: **um erro no código agora é automatizado e replicado em escala**. Uma variável mal definida, uma porta trocada ou um serviço que instala o pacote mas falha ao iniciar pode derrubar dezenas de servidores de produção de uma só vez. Além disso, o fato de o Ansible terminar sem erros de sintaxe (`syntax-check`) não garante que o serviço realmente subiu e está escutando conexões na rede.

É exatamente para fechar essa lacuna que combinamos o **Molecule** e o **Testinfra** antes de qualquer promoção para produção:

- **O papel do ambiente efêmero (Molecule + Docker):** O Molecule atua como o orquestrador de todo o ciclo de vida do teste (`create -> converge -> idempotence -> verify -> destroy`). Em vez de arriscar testes em servidores reais ou manter máquinas virtuais pesadas ligadas o tempo todo, o Molecule conversa com o Docker para levantar um contêiner Ubuntu limpo e descartável (configurado com suporte real ao `systemd` e `cgroups v2`). Esse ambiente efêmero nasce em segundos, recebe a configuração da role do zero e é completamente destruído ao final da bateria, garantindo que nenhum resquício de um teste anterior mascare falhas no próximo.
- **O papel dos asserts automatizados de auditoria (Testinfra + pytest):** Enquanto o Ansible aplica a configuração, o Testinfra entra no contêiner como um auditor independente escrito em Python. Através de asserções diretas (`assert`), ele interroga o estado real do sistema operacional pós-convergência: verifica se o binário está fisicamente instalado (`host.package("nginx").is_installed`), se o daemon está ativo e configurado para o boot no `systemd` (`host.service("nginx").is_running` e `.is_enabled`) e se o socket de rede está efetivamente aberto escutando conexões TCP (`host.socket("tcp://0.0.0.0:80").is_listening`). Se qualquer uma dessas premissas falhar, a esteira é bloqueada imediatamente antes de chegar perto do ambiente de produção.

---

### 4. Exemplo Prático de Mercado: Hardening de Segurança e Conformidade de Bancos de Dados em uma Fintech

Para ilustrar onde essa tríade resolve um problema crítico de negócio **além de um servidor web básico**, considere o cenário de uma **Fintech de meios de pagamento (processamento de transações PIX e cartões)** que mantém um cluster de servidores Linux dedicados a bancos de dados **PostgreSQL** e mensageria interna. Por exigência de auditorias de segurança e normas regulatórias (como **PCI-DSS** e diretrizes do Banco Central), nenhuma máquina que armazena dados financeiros pode operar com configurações padrão de fábrica.

#### O Problema Crítico
A equipe de Segurança da Informação exige que todos os servidores de banco de dados cumpram uma política rigorosa de *Hardening* (blindagem do sistema operacional) e configuração de rede:
1. O acesso SSH com usuário `root` e autenticação por senha deve ser estritamente bloqueado (`/etc/ssh/sshd_config` com `PermitRootLogin no` e `PasswordAuthentication no`).
2. O serviço do PostgreSQL (`postgresql`) deve estar ativo, mas escutando exclusivamente na porta interna criptografada (`5432`) com conexões sem SSL rejeitadas no `pg_hba.conf`.
3. O agente de auditoria e monitoramento de segurança (`auditd`) precisa estar instalado, rodando e habilitado no boot em 100% dos nós.

Fazer isso manualmente em dezenas de nós de banco de dados gerava divergências perigosas (*drift*): bastava um administrador esquecer de reiniciar o `sshd` ou deixar uma permissão aberta em um único servidor para a empresa reprovar na auditoria de segurança ou sofrer um incidente grave.

#### Como Ansible, Molecule e Testinfra resolvem na prática:
1. **Padronização e Idempotência com Ansible:** A engenharia de plataforma cria a role `fintech.hardening_postgres`. Ela instala o `postgresql` e o `auditd`, aplica os templates de segurança do SSH e do banco e garante o estado dos serviços. Graças à idempotência, essa role roda diariamente em todos os servidores garantindo que, se alguém alterar manualmente o `sshd_config`, o Ansible restaure a blindagem sem reiniciar o banco de dados caso o PostgreSQL já esteja no estado correto.
2. **Validação em Ambiente Efêmero com Molecule:** Toda vez que um engenheiro abre um *Pull Request* no GitHub para ajustar um parâmetro de memória do banco ou uma regra de SSH, o pipeline de CI/CD (GitHub Actions) dispara o `molecule test`. O Molecule sobe um contêiner Ubuntu/Debian efêmero com `systemd`, aplica a role de hardening e testa se a segunda execução mantém `changed=0`.
3. **Auditoria de Conformidade com Testinfra:** Antes de o contêiner efêmero ser destruído, o script Python do Testinfra executa os asserts de segurança e operação:
   - `assert host.file("/etc/ssh/sshd_config").contains("PermitRootLogin no")` (garante que o login root está bloqueado);
   - `assert host.service("auditd").is_running and host.service("postgresql").is_running` (garante que nem o banco nem o auditor caíram após o hardening);
   - `assert host.socket("tcp://0.0.0.0:5432").is_listening` (confirma que o banco está aceitando conexões na porta certa).

**Resultado de Negócio:** Se um engenheiro cometer um erro de digitação no arquivo de configuração do PostgreSQL que impeça o banco de subir, o `molecule test` falha em menos de 2 minutos dentro do contêiner descartável do CI/CD. O deploy defeituoso é barrado automaticamente antes de tocar no banco de produção, protegendo a disponibilidade das transações financeiras e mantendo a conformidade contínua da empresa.

---

## Parte 2 — Documentação e Evidências do Laboratório Prático (`servidor_nginx`)

### 1. Estrutura de Diretórios Construída

```text
servidor_nginx/
├── meta/
│   └── main.yml                 # Etapa 1: Identificação FQRN (vinicius.servidor_nginx)
├── tasks/
│   └── main.yml                 # Etapa 2: Instalação apt e serviço systemd do Nginx
└── molecule/
    └── default/
        ├── molecule.yml         # Etapa 3: Orquestração Docker (Ubuntu 22.04 + systemd/cgroups v2)
        ├── converge.yml         # Etapa 4: Playbook de convergência chamando a role
        └── tests/
            └── test_default.py  # Etapa 5: Asserts Python (Testinfra) de pacote, serviço e porta 80
```

### 2. Resumo da Execução Real no GitHub Codespaces

O ciclo completo (`molecule test`) foi executado no ambiente Linux do GitHub Codespaces com todas as etapas aprovadas (`failed=0`):

```text
PLAY [Converge] ****************************************************************
TASK [Gathering Facts] *********************************************************
ok: [ubuntu-teste-nginx]
TASK [Incluir a role servidor_nginx] *******************************************
included: vinicius.servidor_nginx for ubuntu-teste-nginx
TASK [vinicius.servidor_nginx : Instalar o pacote Nginx atualizando o cache do APT] ***
changed: [ubuntu-teste-nginx]
TASK [vinicius.servidor_nginx : Garantir que o servico Nginx esteja iniciado e habilitado no boot] ***
changed: [ubuntu-teste-nginx]

PLAY RECAP (Converge) **********************************************************
ubuntu-teste-nginx         : ok=4    changed=2    unreachable=0    failed=0

PLAY RECAP (Idempotence) *******************************************************
ubuntu-teste-nginx         : ok=4    changed=0    unreachable=0    failed=0

============================= test session starts ==============================
platform linux -- Python 3.14.2, pytest-9.2.0, pluggy-1.7.0
plugins: platformdirs-4.14.0, anyio-4.15.1, testinfra-10.2.2
collected 1 item

tests/test_default.py .                                                  [100%]

============================== 1 passed in 1.38s ===============================

DETAILS                                                                        
default ➜ destroy: Executed: Successful
default ➜ syntax: Executed: Successful
default ➜ create: Executed: Successful
default ➜ converge: Executed: Successful
default ➜ idempotence: Executed: Successful
default ➜ verify: Executed: Successful
default ➜ destroy: Executed: Successful

SCENARIO RECAP                                                                 
default                   : actions=12  successful=6  disabled=0  skipped=0  missing=6  failed=0
```
