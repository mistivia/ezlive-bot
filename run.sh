sudo podman kill ezlivebot-c
sudo podman rm ezlivebot-c
sudo podman run --rm -it --name ezlivebot-c -v $(pwd):/app/ ezlivebot-rt
