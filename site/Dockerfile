FROM nginx:alpine

# Copy built site
COPY dist/ /usr/share/nginx/html/

# Nginx config for clean URLs (trailing slash -> index.html)
RUN printf 'server {\n\
  listen 80;\n\
  root /usr/share/nginx/html;\n\
  index index.html;\n\
  location / {\n\
    try_files $uri $uri/ $uri/index.html =404;\n\
  }\n\
}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
