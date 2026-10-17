"""Gera o SVG editável dos três estados; PNG é exportado por Sharp."""
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'diagrams'
parts = []


def rect(x, y, w, h, fill='#ffffff', stroke='#d2dce8', radius=16, dash=None):
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="2"' + (f' stroke-dasharray="{dash}"' if dash else '') + '/>')


def text(x, y, value, size=23, color='#16283d', weight=400, anchor='start'):
    parts.append(f'<text x="{x}" y="{y}" font-family="Segoe UI,DejaVu Sans,sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{escape(value)}</text>')


def node(x, y, w, title, lines, *, fill='#fff', stroke='#9aadc1', h=140):
    rect(x, y, w, h, fill, stroke)
    text(x+20, y+36, title, 25, weight=650)
    for i, line in enumerate(lines):
        text(x+20, y+72+i*30, line, 20)


def arrow(points, label='', color='#2467ae', lx=None, ly=None, dash=False):
    coords = ' '.join(f'{x},{y}' for x,y in points)
    parts.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="4" marker-end="url(#arrow-{color[1:]})"' + (' stroke-dasharray="8 6"' if dash else '') + '/>')
    if label:
        x, y = lx if lx is not None else points[0][0]+15, ly if ly is not None else (points[0][1]+points[-1][1])/2
        text(x, y, label, 21, color, 600)


def database(x, y, w=390):
    # Cilindro: notação de banco de dados.
    parts.append(f'<path d="M{x},{y+25} v110 a{w/2},25 0 0 0 {w},0 v-110" fill="#eaf3f9" stroke="#809db8" stroke-width="2"/>')
    parts.append(f'<ellipse cx="{x+w/2}" cy="{y+25}" rx="{w/2}" ry="25" fill="#f5f9fc" stroke="#809db8" stroke-width="2"/>')
    text(x+20, y+70, 'PostgreSQL · TCP 5432', 24, weight=650)
    text(x+20, y+102, 'Rede database · interna', 21)
    text(x+20, y+132, 'Sem porta no host', 21)


def draw():
    parts.clear()
    parts.append('<svg xmlns="http://www.w3.org/2000/svg" width="2500" height="1840" viewBox="0 0 2500 1840">')
    parts.append('<defs>')
    for color in ['2467ae','b34237','16715c','788899']:
        parts.append(f'<marker id="arrow-{color}" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="9" markerHeight="9" orient="auto-start-reverse"><path d="M0 0 L12 6 L0 12 Z" fill="#{color}"/></marker>')
    parts.append('</defs>')
    rect(0,0,2500,1840,'#f5f8fc','#f5f8fc',0)
    text(60,70,'A rede de um servidor com n8n',44,weight=700)
    text(60,116,'Três estados de exposição · Arquitetura de referência de uma VPS Linux própria',25,'#52647a')
    text(60,156,'As setas mostram o sentido da requisição/conexão; as respostas retornam na mesma sessão.',21,'#52647a')
    data = [
        ('01','EXPOSTO','#b34237','Qualquer cliente alcança o n8n diretamente.'),
        ('02','ATRÁS DO PROXY','#2467ae','HTTPS e autenticação na borda.'),
        ('03','ADMINISTRAÇÃO POR VPN','#16715c','SSH e painel só pela rede WireGuard.')]
    for index,(number,title,color,subtitle) in enumerate(data):
        x=50+index*820
        rect(x,200,780,1370,'#ffffff','#d2dce8',20)
        rect(x,200,780,110,'#eaf0f7',color,20)
        text(x+22,240,number,24,color,700)
        text(x+75,240,title,27,color,700)
        text(x+22,282,subtitle,21,'#425a72')
        node(x+28,340,724,'INTERNET / CLIENTES',
             ['Navegador, administrador remoto e produtor de eventos'],fill='#f8fafc',h=100)
        # Fronteira da VPS, distinguindo INPUT e tráfego encaminhado Docker.
        rect(x+16,480,748,1068,'#fafcfe','#94a7bd',12,'9 6')
        text(x+32,510,'VPS · limite de confiança',20,'#52647a',600)
        firewall_lines = [
            ['5678/TCP publicada (DNAT Docker)','22/TCP: serviço SSH do host'],
            ['80/443 TCP públicos; SSH 22 somente por chave','5678/5432 sem publicação no host'],
            ['51820/UDP público; 443/TCP se houver webhook','22/TCP e painel 443 só em wg0']][index]
        node(x+28,535,724,'FIREWALL + REGRAS DO DOCKER',firewall_lines,fill='#edf2f7',h=136)
        arrow([(x+390,440),(x+390,533)],'entrada',color,lx=x+410,ly=486)
        # Serviço host: SSH separado dos containers.
        if index<2:
            node(x+35,760,220,'SSH · 22/TCP',
                 ['Administração', 'Somente chave' if index else 'Acesso remoto'],fill='#f1f5f9',h=132)
            arrow([(x+140,671),(x+140,758)],'22/TCP',color,lx=x+157,ly=718)
        else:
            node(x+35,1030,220,'SSH · 22/TCP',['Só em wg0','Somente chave'],fill='#eaf6f2',stroke=color,h=132)
        if index==0:
            rect(x+290,710,450,803,'#f7fafc','#afbfcd',14,'6 5')
            text(x+308,740,'Redes Docker privadas',20,'#52647a',600)
            node(x+310,805,410,'PROXY: AUSENTE',['Sem TLS na borda','Nenhuma filtragem de rotas'],fill='#f7f8fa',stroke='#c3cbd4',h=140)
            node(x+310,1025,410,'n8n · TCP 5678',['HTTP alcançável pela internet','Painel, REST e webhooks'],fill='#fff1ed',stroke=color,h=140)
            arrow([(x+685,671),(x+685,760),(x+755,760),(x+755,1095),(x+722,1095)],'5678/TCP · HTTP',color,lx=x+400,ly=993)
            database(x+320,1340,390)
            arrow([(x+515,1165),(x+515,1338)],'5432/TCP',lx=x+530,ly=1260)
        elif index==1:
            rect(x+290,710,450,803,'#f7fafc','#afbfcd',14,'6 5')
            text(x+308,740,'Containers Docker',20,'#52647a',600)
            node(x+310,805,410,'TRAEFIK · 80 / 443',['80 redireciona para HTTPS','443: TLS + BasicAuth'],fill='#eef5fd',stroke=color,h=140)
            arrow([(x+515,671),(x+515,803)],'80/443 TCP',color,lx=x+530,ly=769)
            node(x+310,1025,410,'n8n · TCP 5678',['Login nativo + header no webhook','Sem ports: no Compose'],fill='#eef5fd',stroke=color,h=140)
            arrow([(x+515,945),(x+515,1023)],'5678/TCP · HTTP interno',color,lx=x+330,ly=990)
            database(x+320,1340,390)
            arrow([(x+515,1165),(x+515,1338)],'5432/TCP · rede database',lx=x+316,ly=1260)
        else:
            node(x+310,735,410,'WIREGUARD · wg0',['51820/UDP: túnel autenticado','10.77.0.0/24 · admin autorizado'],fill='#eaf6f2',stroke=color,h=140)
            arrow([(x+515,671),(x+515,733)],'51820/UDP',color,lx=x+530,ly=718)
            rect(x+290,910,450,633,'#f7fafc','#afbfcd',14,'6 5')
            text(x+308,940,'Containers Docker',20,'#52647a',600)
            node(x+310,975,410,'TRAEFIK · HTTPS',['Painel: bind no IP de wg0','Webhook: IP público separado'],fill='#eaf6f2',stroke=color,h=140)
            arrow([(x+515,875),(x+515,973)],'443/TCP via VPN',color,lx=x+530,ly=904)
            arrow([(x+310,805),(x+145,805),(x+145,1028)],'SSH via túnel',color,lx=x+43,ly=973)
            arrow([(x+700,671),(x+755,671),(x+755,1040),(x+722,1040)],'', '#2467ae')
            text(x+333,1197,'443 público: só POST /webhook/ares-lab',19,'#2467ae',600)
            node(x+310,1230,410,'n8n · TCP 5678',['Webhook exige token de header','Painel/REST bloqueados na rota pública'],fill='#eaf6f2',stroke=color,h=132)
            arrow([(x+515,1115),(x+515,1228)],'5678/TCP interno',color,lx=x+530,ly=1158)
            database(x+320,1390,390)
            arrow([(x+515,1362),(x+515,1388)],'',color)
        if index<2:
            text(x+38,1450,'VPN:',21,'#52647a',600)
            text(x+38,1484,'inativa',21,'#52647a')
        else:
            text(x+38,1405,'Sem webhook:',20,'#52647a',600)
            text(x+38,1438,'fechar 443',20,'#52647a')
            text(x+38,1471,'público também.',20,'#52647a')
    rect(50,1600,2400,200,'#eaf0f7','#d2dce8')
    text(75,1640,'LEITURA E CORRESPONDÊNCIA COM O REPOSITÓRIO',24,weight=700)
    text(75,1680,'01 é referência de risco: a baseline da auditoria usa CLI sem rede/portas. 02 é implementado pelo Compose do laboratório.',22)
    text(75,1716,'02 e 03 implantados na VPS Ubuntu de teste: 02 com SSH/UFW; 03 com WireGuard em 51820/udp e painel/SSH somente via wg0 (verification-vpn.json).',22)
    text(75,1752,'No teste local: HTTP 18080; painel HTTPS 18443; entrada exclusiva de webhook HTTPS 19443 — todos em 127.0.0.1.',22)
    text(75,1785,'UFW INPUT não basta para portas publicadas pelo Docker. O controle decisivo é não publicar n8n/PostgreSQL.',21,'#52647a')
    parts.append('</svg>')
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'n8n-three-states.svg').write_text('\n'.join(parts),encoding='utf-8',newline='\n')
    print('SVG editável exportado.')


if __name__=='__main__':
    draw()
