#!/bin/bash

# This is useful when running the CI locally, while it is not necessary when using the ci.yml GitHub action.
docker run \
    --rm \
    -d  \
    --name openssh \
    -p 2222:2222 \
    -e PASSWORD_ACCESS=true \
    -e USER_PASSWORD=pass \
    -e USER_NAME=user \
    linuxserver/openssh-server \
&&
docker run \
    --name=mailpit \
    -p 8025:8025 \
    -p 1025:1025 \
    -e MP_SMTP_AUTH="sender@example.org:fakepassword" \
    -e MP_SMTP_AUTH_ALLOW_INSECURE=true \
    axllent/mailpit

