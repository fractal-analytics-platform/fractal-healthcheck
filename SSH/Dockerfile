FROM alpine:3.21


# COPY ./entrypoint.sh /
# RUN chmod +x /entrypoint.sh
# RUN ls /

RUN apk add openssh openrc

# RUN sed -i s/#PermitRootLogin.*/PermitRootLogin\ yes/ /etc/ssh/sshd_config
#RUN echo "root:password" | chpasswd
RUN echo "rc-service sshd start" > "/run.sh"
RUN chmod +x /run.sh

EXPOSE 22
ENTRYPOINT ["ls", " /"]
