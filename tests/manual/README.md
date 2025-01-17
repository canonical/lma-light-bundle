# Manual tests

## 3-node cluster in a multipass VM (nested virtualization)
The [`microk8s-ha.yaml`](microk8s-ha.yaml) file contains a cloud-init script
for an "all in one" VM. When launched the VM will have three nested VMs called
"node-1", "node-2" and "node-3".

```mermaid
graph LR

subgraph microk8s-ha multipass VM

subgraph node-0 multipass VM
microk8s_0[microk8s]
end

subgraph node-1 multipass VM
microk8s_1[microk8s]
end

subgraph node-2 multipass VM
microk8s_2[microk8s]
end

juju

end
```

Launch the VM with:
```bash
multipass launch 22.04 --cloud-init microk8s-ha.yaml \
 --timeout 2000 \
 --name three-node \
 --memory 32G \
 --cpus 16 \
 --disk 160G
```

Then shell into the vm, get the `three-nodes-overlay.yaml` file and run:
```bash
juju deploy --trust cos-lite --overlay ./three-nodes-overlay.yaml
```

From within the "outer VM" you can `multipass exec` into the node VMs:
```bash
multipass exec node-1 microk8s.kubectl -n welcome-k8s get pods -A
```

Note that with Juju <3.3.5,<3.4.4, you would need to manually patch the
statefulsets due to a [bug](https://bugs.launchpad.net/juju/+bug/2062934).
