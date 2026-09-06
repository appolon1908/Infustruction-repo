# Port exposure

codestra-agent-desktop-preview	127.0.0.1:31880->80/tcp
codestra-agent-desktop-sipjs-staging	127.0.0.1:31881->8080/tcp
codestra-appolon-middleware-integration-api-1	8080/tcp
codestra-backup-1	5432/tcp
codestra-beyvra-email-api-1	
codestra-caddy-upstream-gateway	80/tcp, 443/tcp, 2019/tcp, 443/udp, 127.0.0.1:18101-18116->18101-18116/tcp
codestra-email-reseller-api-1	127.0.0.1:18180->8080/tcp
codestra-identity-auth-gateway-1	4180/tcp
codestra-identity-identity-db-1	5432/tcp
codestra-identity-keycloak-1	8080/tcp, 8443/tcp, 9000/tcp
codestra-identity-staging-identity-db-staging-1	5432/tcp
codestra-identity-staging-keycloak-staging-1	8080/tcp, 8443/tcp, 9000/tcp
codestra-integration-control-plane-api-1	127.0.0.1:8096->8096/tcp
codestra-integration-control-plane-worker-1	
codestra-kong-identity-certification-1	
codestra-kong-kong-db-1	5432/tcp
codestra-kong-kong-gateway-1	8003-8004/tcp, 127.0.0.1:8000-8002->8000-8002/tcp, 8443-8447/tcp
codestra-kong-kong-test-upstream-1	80/tcp
codestra-kong-service-auth-adapter-1	
codestra-mail-api-mail-api-1	8098/tcp
codestra-mail-isolated-stalwart-1	25/tcp, 110/tcp, 143/tcp, 465/tcp, 995/tcp, 4190/tcp, 127.0.0.1:28443->443/tcp, 127.0.0.1:2587->587/tcp, 127.0.0.1:2993->993/tcp, 127.0.0.1:28080->8080/tcp
codestra-middleware-1	8095/tcp
codestra-middleware-breero-odoo-worker-1	8095/tcp
codestra-middleware-event-gateway-1	8095/tcp
codestra-middleware-evidence-runner-1	8095/tcp
codestra-middleware-extension-allocator-1	8095/tcp
codestra-middleware-external-webhook-worker-1	8095/tcp
codestra-middleware-integration-api-1	8095/tcp
codestra-middleware-n8n-runtime-worker-1	8095/tcp
codestra-middleware-notification-worker-1	8095/tcp
codestra-middleware-odoo-result-worker-1	8095/tcp
codestra-middleware-pjsip-adapter-1	8095/tcp
codestra-middleware-policy-engine-1	8095/tcp
codestra-middleware-postly-polling-worker-1	8095/tcp
codestra-middleware-reconciliation-worker-1	8095/tcp
codestra-middleware-scheduler-1	8095/tcp
codestra-middleware-scraper-odoo-delivery-worker-1	8095/tcp
codestra-middleware-social-n8n-delivery-worker-1	8095/tcp
codestra-middleware-staging-callback-staging-1	8095/tcp, 8443/tcp
codestra-middleware-staging-middleware-staging-1	127.0.0.1:31883->8095/tcp
codestra-middleware-staging-notification-worker-staging-1	8095/tcp
codestra-middleware-staging-odoo-result-worker-staging-1	8095/tcp
codestra-middleware-staging-postgres-1	5432/tcp
codestra-middleware-staging-redis-1	6379/tcp
codestra-middleware-staging-scheduler-staging-1	8095/tcp
codestra-middleware-staging-scraper-odoo-delivery-worker-1	8095/tcp
codestra-middleware-staging-social-dead-letter-worker-staging-1	8095/tcp
codestra-middleware-staging-social-delivery-worker-staging-1	8095/tcp
codestra-middleware-staging-social-reconciliation-worker-staging-1	8095/tcp
codestra-middleware-sync-worker-1	8095/tcp
codestra-middleware-telephony-provisioning-1	8095/tcp
codestra-middleware-vicidial-adapter-1	8095/tcp
codestra-middleware-webphone-session-issuer-1	8095/tcp
codestra-monitoring-alertmanager-1	9093/tcp
codestra-monitoring-blackbox-1	9115/tcp
codestra-monitoring-cadvisor-1	8080/tcp
codestra-monitoring-node-exporter-1	9100/tcp
codestra-monitoring-prometheus-1	9090/tcp
codestra-monitoring-receiver-receiver-1	
codestra-monitoring-redis-exporter-1	9121/tcp
codestra-n8n-1	5678/tcp
codestra-n8n-internal-proxy	80/tcp, 443/tcp, 2019/tcp, 443/udp
codestra-n8n-staging-n8n-1	5678/tcp
codestra-n8n-staging-postgres-1	5432/tcp
codestra-n8n-staging-redis-1	6379/tcp
codestra-n8n-staging-webhook-1	5678/tcp
codestra-n8n-staging-worker-1	5678/tcp
codestra-n8n-staging-worker-2-1	5678/tcp
codestra-odoo-1	8069/tcp, 8071-8072/tcp
codestra-odoo-internal-proxy	80/tcp, 443/tcp, 2019/tcp, 443/udp
codestra-odoo-staging-odoo-staging-1	8069/tcp, 8071-8072/tcp
codestra-odoo-staging-postgres-staging-1	5432/tcp
codestra-odoo-staging-uat-loopback-proxy-1	127.0.0.1:19069->19069/tcp
codestra-odoo19-identity-menu-staging-postgres-1	5432/tcp
codestra-odoo19-module-staging-callback-tls-1	80/tcp, 443/tcp, 2019/tcp, 443/udp
codestra-odoo19-module-staging-odoo-1	8069/tcp, 8071-8072/tcp
codestra-odoo19-module-staging-postgres-1	5432/tcp
codestra-odoo19-staging-odoo19-master-staging-1	8069/tcp, 8071-8072/tcp
codestra-odoo19-staging-odoo19-scraper-canary-1	8069/tcp, 8071-8072/tcp
codestra-odoo19-staging-odoo19-staging-1	8069/tcp, 8071-8072/tcp
codestra-odoo19-staging-postgres-1	5432/tcp
codestra-operations-dashboard-grafana-grafana-1	127.0.0.1:3000->3000/tcp
codestra-operations-dashboard-staging-v2-middleware-1	8080/tcp
codestra-operations-dashboard-staging-v2-postgres-1	5432/tcp
codestra-operations-dashboard-staging-v2-redis-1	6379/tcp
codestra-postgres-1	5432/tcp
codestra-private-vicidial-ingress-1	80/tcp, 2019/tcp, 10.40.0.1:443->443/tcp, 443/udp
codestra-provisioning-jwks-relay	8443/tcp
codestra-provisioning-service-provisioning-service-1	8443/tcp
codestra-redis-1	6379/tcp
codestra-reseller-portal-oidc-gateway-1	
codestra-reseller-portal-portal-1	127.0.0.1:18081->8080/tcp
codestra-reseller-portal-postgres-1	5432/tcp
codestra-reviewed-monitoring-postgres-exporter-1	9187/tcp
codestra-sms-api-api-1	8080/tcp
codestra-sms-api-event-worker-1	8080/tcp
codestra-sms-api-postgres-1	5432/tcp
codestra-websocket-gateway-gateway-1	8080/tcp
codestra-websocket-gateway-postgres-1	5432/tcp
codestra-websocket-replica-postgres-1	5432/tcp
kong-production-standby-kong-standby-auth-1	
private-integration-gateway-1	10.40.0.1:8095->8080/tcp

Netid State  Recv-Q Send-Q Local Address:Port  Peer Address:PortProcess                                   
udp   UNCONN 0      0          10.40.0.1:18080      0.0.0.0:*    users:(("caddy",pid=16620,fd=11))        
udp   UNCONN 0      0      127.0.0.53%lo:53         0.0.0.0:*    users:(("systemd-resolve",pid=843,fd=13))
udp   UNCONN 0      0      65.109.65.169:443        0.0.0.0:*    users:(("caddy",pid=16620,fd=15))        
udp   UNCONN 0      0          127.0.0.1:443        0.0.0.0:*    users:(("caddy",pid=16620,fd=13))        
tcp   LISTEN 0      4096       127.0.0.1:8001       0.0.0.0:*    users:(("docker-proxy",pid=174736,fd=8)) 
tcp   LISTEN 0      4096       127.0.0.1:8000       0.0.0.0:*    users:(("docker-proxy",pid=174647,fd=8)) 
tcp   LISTEN 0      4096       127.0.0.1:8002       0.0.0.0:*    users:(("docker-proxy",pid=174756,fd=8)) 
tcp   LISTEN 0      4096       127.0.0.1:8096       0.0.0.0:*    users:(("docker-proxy",pid=7533,fd=8))   
tcp   LISTEN 0      4096       127.0.0.1:4222       0.0.0.0:*    users:(("nats-server",pid=862,fd=8))     
tcp   LISTEN 0      4096       127.0.0.1:3000       0.0.0.0:*    users:(("docker-proxy",pid=9495,fd=8))   
tcp   LISTEN 0      4096       127.0.0.1:2993       0.0.0.0:*    users:(("docker-proxy",pid=7752,fd=8))   
tcp   LISTEN 0      4096       127.0.0.1:2587       0.0.0.0:*    users:(("docker-proxy",pid=7730,fd=8))   
tcp   LISTEN 0      128        127.0.0.1:443        0.0.0.0:*    users:(("caddy",pid=16620,fd=3))         
tcp   LISTEN 0      128        127.0.0.1:80         0.0.0.0:*    users:(("caddy",pid=16620,fd=21))        
tcp   LISTEN 0      4096       10.40.0.1:8095       0.0.0.0:*    users:(("docker-proxy",pid=10559,fd=8))  
tcp   LISTEN 0      128        10.40.0.1:80         0.0.0.0:*    users:(("caddy",pid=16620,fd=20))        
tcp   LISTEN 0      4096       127.0.0.1:8222       0.0.0.0:*    users:(("nats-server",pid=862,fd=7))     
tcp   LISTEN 0      4096       10.40.0.1:443        0.0.0.0:*    users:(("docker-proxy",pid=5560,fd=8))   
tcp   LISTEN 0      128          0.0.0.0:22         0.0.0.0:*    users:(("sshd",pid=1055,fd=3))           
tcp   LISTEN 0      4096       127.0.0.1:19069      0.0.0.0:*    users:(("docker-proxy",pid=8527,fd=8))   
tcp   LISTEN 0      4096       127.0.0.1:18180      0.0.0.0:*    users:(("docker-proxy",pid=14008,fd=8))  
tcp   LISTEN 0      4096       127.0.0.1:18116      0.0.0.0:*    users:(("docker-proxy",pid=236418,fd=8)) 
tcp   LISTEN 0      4096       127.0.0.1:18113      0.0.0.0:*    users:(("docker-proxy",pid=236366,fd=8)) 
tcp   LISTEN 0      4096       127.0.0.1:18112      0.0.0.0:*    users:(("docker-proxy",pid=236351,fd=8)) 
tcp   LISTEN 0      4096       127.0.0.1:18115      0.0.0.0:*    users:(("docker-proxy",pid=236400,fd=8)) 
tcp   LISTEN 0      4096       127.0.0.1:18114      0.0.0.0:*    users:(("docker-proxy",pid=236383,fd=8)) 
tcp   LISTEN 0      4096       127.0.0.1:18109      0.0.0.0:*    users:(("docker-proxy",pid=236298,fd=8)) 
tcp   LISTEN 0      4096       127.0.0.1:18108      0.0.0.0:*    users:(("docker-proxy",pid=236282,fd=8)) 
tcp   LISTEN 0      4096       127.0.0.1:18111      0.0.0.0:*    users:(("docker-proxy",pid=236334,fd=8)) 
tcp   LISTEN 0      4096       127.0.0.1:18110      0.0.0.0:*    users:(("docker-proxy",pid=236316,fd=8)) 
tcp   LISTEN 0      4096       127.0.0.1:18105      0.0.0.0:*    users:(("docker-proxy",pid=236233,fd=8)) 
tcp   LISTEN 0      4096       127.0.0.1:18104      0.0.0.0:*    users:(("docker-proxy",pid=236217,fd=8)) 
tcp   LISTEN 0      4096       127.0.0.1:18107      0.0.0.0:*    users:(("docker-proxy",pid=236265,fd=8)) 
tcp   LISTEN 0      4096       127.0.0.1:18106      0.0.0.0:*    users:(("docker-proxy",pid=236248,fd=8)) 
tcp   LISTEN 0      4096       127.0.0.1:18101      0.0.0.0:*    users:(("docker-proxy",pid=236169,fd=8)) 
tcp   LISTEN 0      4096       127.0.0.1:18103      0.0.0.0:*    users:(("docker-proxy",pid=236201,fd=8)) 
tcp   LISTEN 0      4096       127.0.0.1:18102      0.0.0.0:*    users:(("docker-proxy",pid=236185,fd=8)) 
tcp   LISTEN 0      4096       127.0.0.1:18081      0.0.0.0:*    users:(("docker-proxy",pid=12827,fd=8))  
tcp   LISTEN 0      4096       127.0.0.1:31881      0.0.0.0:*    users:(("docker-proxy",pid=9388,fd=8))   
tcp   LISTEN 0      4096       127.0.0.1:31880      0.0.0.0:*    users:(("docker-proxy",pid=8898,fd=8))   
tcp   LISTEN 0      4096       127.0.0.1:31883      0.0.0.0:*    users:(("docker-proxy",pid=10724,fd=8))  
tcp   LISTEN 0      4096       127.0.0.1:28443      0.0.0.0:*    users:(("docker-proxy",pid=7707,fd=8))   
tcp   LISTEN 0      4096   127.0.0.53%lo:53         0.0.0.0:*    users:(("systemd-resolve",pid=843,fd=14))
tcp   LISTEN 0      4096       127.0.0.1:28080      0.0.0.0:*    users:(("docker-proxy",pid=7769,fd=8))   
tcp   LISTEN 0      128        10.40.0.1:18080      0.0.0.0:*    users:(("caddy",pid=16620,fd=24))        
tcp   LISTEN 0      128    65.109.65.169:80         0.0.0.0:*    users:(("caddy",pid=16620,fd=23))        
tcp   LISTEN 0      128    65.109.65.169:443        0.0.0.0:*    users:(("caddy",pid=16620,fd=18))        
tcp   LISTEN 0      128             [::]:22            [::]:*    users:(("sshd",pid=1055,fd=4))           
