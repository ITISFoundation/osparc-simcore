# Dynamic modeling service using a [qooxdoo](http://qooxdoo.org/) + [three.js](https://threejs.org/) client and a [node.js] (https://nodejs.org/) server

## Hybrid swarm (Windows tips)
### multiple network adapters
Check the Hyper-V manager in the switch manager. When joining the swarm docker creates a virtual network named as the network ID. Check that this
network actually uses the right adapter.