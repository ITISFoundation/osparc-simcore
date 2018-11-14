docker pull certbot/certbot

sudo docker run -it --rm --name letsencrypt \
 -v "${PWD}/nginx/ssl:/etc/letsencrypt" \
 --volumes-from registry_nginx_1 \
 certbot/certbot \
 certonly \
 --webroot \
 --webroot-path /var/www/registry.simcore.io \
 --agree-tos \
 --renew-by-default \
 -d registry.simcore.io \
 -m guidon@itis.ethz.ch

## this script should run monthly as a cronjob
## because certificates are only valid for 90 days
## after renewal, the nginx deamon needs to be restarted
# docker-compose down
# docker-compose up -d
