# cloud_ddos_automation
WIP for cloud ddos automation using goBGP

## add prefix to cloud scrubbing logic
![alt text](https://github.com/cpmarvin/cloud_ddos_automation/blob/master/generic_ddos_automation_add.png?raw=true)


## remove prefix from cloud scrubbing
![alt text](https://github.com/cpmarvin/cloud_ddos_automation/blob/master/generic_ddos_automation_remove.png?raw=true)


## PoC

```
lab@ke-pe3-nbi> show route community 1111:800 table inet.0

inet.0: 19 destinations, 25 routes (19 active, 0 holddown, 0 hidden)
@ = Routing Use Only, # = Forwarding Use Only
+ = Active Route, - = Last Active, * = Both

10.0.0.0/8         *[BGP/170] 00:00:29, localpref 100, from 10.7.7.7
                      AS path: I, validation-state: unverified
                    > to 10.22.33.22 via ge-0/0/3.0, Push 201007
                      to 10.2.3.2 via ge-0/0/0.0, Push 201007
10.100.0.0/24      *[BGP/170] 00:00:29, localpref 100, from 10.7.7.7
                      AS path: I, validation-state: unverified
                    > to 10.22.33.22 via ge-0/0/3.0, Push 201007
                      to 10.2.3.2 via ge-0/0/0.0, Push 201007
                      
python3 cloud_ddos.py -a 10.200.1.1
DDoS Attack start , action add for 10.200.1.1/32
Subnet not found ... starting bgp inject workflow
found supernet 10.0.0.0/8 ... inject 10.200.1.0/24 subnet with next-hop 10.7.7.7
Configure routers to allow subnet 10.200.1.0/24 to DDoS Cloud Scrubbing
Configure routers to deny subnet 10.200.1.0/24 to all external peers

lab@ke-pe3-nbi> show route community 1111:800 table inet.0

inet.0: 20 destinations, 26 routes (20 active, 0 holddown, 0 hidden)
@ = Routing Use Only, # = Forwarding Use Only
+ = Active Route, - = Last Active, * = Both

10.0.0.0/8         *[BGP/170] 00:02:59, localpref 100, from 10.7.7.7
                      AS path: I, validation-state: unverified
                    > to 10.22.33.22 via ge-0/0/3.0, Push 201007
                      to 10.2.3.2 via ge-0/0/0.0, Push 201007
10.100.0.0/24      *[BGP/170] 00:02:59, localpref 100, from 10.7.7.7
                      AS path: I, validation-state: unverified
                    > to 10.22.33.22 via ge-0/0/3.0, Push 201007
                      to 10.2.3.2 via ge-0/0/0.0, Push 201007
10.200.1.0/24      *[BGP/170] 00:00:48, localpref 100, from 172.16.0.2
                      AS path: 64512 E, validation-state: unverified
                    > to 10.22.33.22 via ge-0/0/3.0, Push 201007
                      to 10.2.3.2 via ge-0/0/0.0, Push 201007
                      
```
