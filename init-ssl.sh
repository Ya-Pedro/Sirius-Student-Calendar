#!/bin/bash
set -e

DOMAIN="pedro.ittori.ru"
EMAIL="pedro@ittori.ru"

mkdir -p certbot/conf certbot/www

echo ">>> Генерация временного сертификата..."
mkdir -p certbot/conf/live/$DOMAIN
openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
  -keyout certbot/conf/live/$DOMAIN/privkey.pem \
  -out certbot/conf/live/$DOMAIN/fullchain.pem \
  -subj "/CN=$DOMAIN"

echo ">>> Запуск контейнеров..."
docker-compose up -d

echo ">>> Удаление временного сертификата..."
rm -rf certbot/conf/live/$DOMAIN
rm -rf certbot/conf/archive/$DOMAIN
rm -rf certbot/conf/renewal/$DOMAIN.conf

echo ">>> Получение сертификата Let's Encrypt..."
docker-compose run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email $EMAIL \
  --agree-tos \
  --no-eff-email \
  -d $DOMAIN

echo ">>> Перезапуск nginx..."
docker-compose restart nginx

echo ">>> Готово!"
echo "    https://$DOMAIN:8080/schedule.ics — К0609-23"
echo "    https://$DOMAIN:8081/schedule.ics — К0409-24"
