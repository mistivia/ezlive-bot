rsync -avz ./ root@raye:./ezlivebot/
ssh root@raye 'podman restart ezlivebot-c'