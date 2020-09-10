import sys
import re
import argparse
import grpc
from google.protobuf.any_pb2 import Any

import gobgp_pb2
import gobgp_pb2_grpc
import attribute_pb2
from config import CIDR_COMM
from config import SCRUB_COMM

#helpers
def pb_msg_attrs(m):
  # return list of attr names
  slice_ind = -1 * len('_FIELD_NUMBER')
  attrs = [ attr[:slice_ind].lower() for attr in dir(m) if attr.endswith('_FIELD_NUMBER') ]
  if attrs:
    return attrs
  # temporary workaround for an issue with python3 generated message classes that include no field number constants.
  return [ attr for attr in dir(m) if re.match(r'[a-z]', attr) ]

def get_subnet(ip_address):
    '''
    return /24 subnet from ip
    '''
    list_ = ip_address.split('.')
    assert len(list_) == 4
    list_[3] = '0'
    ip = '.'.join(list_)
    subnet = ip + '/24'
    return subnet

#end helpers

def go_bgp_check_supernet(stub,subnet):
    '''
    Check if there is a route for the /24 subnet in table with COMM ACME-CIDR
    return route and next-hop
    '''
    result = {
        'found':False,
        'route':'',
        'next-hop':''}
    subnet  = subnet.split('/')[0]
    prefixes = []
    prefixes.append(gobgp_pb2.TableLookupPrefix(prefix=subnet))
    res = stub.ListPath(
        gobgp_pb2.ListPathRequest(
            table_type = gobgp_pb2.GLOBAL,
            family=gobgp_pb2.Family(afi=gobgp_pb2.Family.AFI_IP, safi=gobgp_pb2.Family.SAFI_UNICAST),
            prefixes=prefixes
        )
    )
    destinations = [ d for d in res ]
    if len(destinations) > 0:
        for path in [ p for d in destinations for p in d.destination.paths ]:
            #print(path)
            nlri = attribute_pb2.IPAddressPrefix()
            path.nlri.Unpack(nlri)
            route = str("{}/{}".format(nlri.prefix, nlri.prefix_len))
            result['route'] = route
            pattrs = []
            for attr_name in pb_msg_attrs(path):
                if attr_name == "nlri":
                    continue
                if attr_name == "pattrs":
                    for pattr in path.pattrs:
                        pattr_name = pattr.type_url.split(".")[-1]
                        pattr_cls = getattr(attribute_pb2, pattr_name, None)
                        if pattr_cls:
                            pattr_obj = pattr_cls()
                            pattr.Unpack(pattr_obj)
                            for k in pb_msg_attrs(pattr_obj):
                                if k == "communities":
                                    v = [ str("{}:{}".format(int("0xffff",16)&c>>16, int("0xffff",16)&c)) for c in getattr(pattr_obj, k, []) ]
                                    if CIDR_COMM in v:
                                        result['found'] = True
                                if k == "next_hop":
                                    v = str(getattr(pattr_obj, k, "")).strip().replace("\n", ", ")
                                    result['next-hop'] = v

    return result


def go_bgp_subnet(stub,subnet,nh,delete=False):
    '''
    inject or delete an route with <ACME>-CIDR and <ACME>-SCRUBBING community
    '''
    family = gobgp_pb2.Family(afi=gobgp_pb2.Family.AFI_IP, safi=gobgp_pb2.Family.SAFI_UNICAST)
    timeout_seconds = 10
    community = CIDR_COMM + ',' + SCRUB_COMM
    comms = []
    for s in community.split(","):
        comms.append((int(s.split(':')[0]) << 16) + int(s.split(':')[1]))

    attributes = []

    nlri = Any()
    prefix = subnet.split("/")[0]
    prefix_len = int(subnet.split("/")[1])
    nlri.Pack(attribute_pb2.IPAddressPrefix(
        prefix_len=prefix_len,
        prefix=prefix,
    ))

    #next-hop
    next_hop = Any()
    next_hop.Pack(attribute_pb2.NextHopAttribute(
        next_hop=nh,
    ))
    attributes.append(next_hop)

    if not delete:
        #Origin
        origin = Any()
        origin.Pack(attribute_pb2.OriginAttribute(origin=1))
        attributes.append(origin)
        #Communities
        communities = Any()
        communities.Pack(attribute_pb2.CommunitiesAttribute(communities = comms,))
        attributes.append(communities)
   

    if delete:
        #print(f'Delete {nlri} {attributes}')
        stub.DeletePath(
            gobgp_pb2.DeletePathRequest(
                table_type=gobgp_pb2.GLOBAL,
                path=gobgp_pb2.Path(
                    nlri=nlri,
                    pattrs=attributes,
                    family=family
                )
            ),
        timeout_seconds,
        )
    else:
        #print(f'Inject {nlri} {attributes}')
        stub.AddPath(
            gobgp_pb2.AddPathRequest(
                table_type=gobgp_pb2.GLOBAL,
                path=gobgp_pb2.Path(
                    nlri=nlri,
                    pattrs=attributes,
                    family=family
                )
            ),
            timeout_seconds,
        )


def go_bgp_check_subnet(stub,subnet,scrub_community = False,exact = True):
    subnet_info = {
        "found":False,
        "subnet":subnet,
        "community_scrub":False,
        "communities":[]}
    prefixes = []
    prefixes.append(gobgp_pb2.TableLookupPrefix(prefix=subnet))
    res = stub.ListPath(
        gobgp_pb2.ListPathRequest(
            table_type = gobgp_pb2.GLOBAL,
            family=gobgp_pb2.Family(afi=gobgp_pb2.Family.AFI_IP, safi=gobgp_pb2.Family.SAFI_UNICAST),
            prefixes=prefixes
        )
    )
    destinations = [ d for d in res ]
    if len(destinations) > 0:
        for path in [ p for d in destinations for p in d.destination.paths ]:
            #print(path)
            nlri = attribute_pb2.IPAddressPrefix()
            path.nlri.Unpack(nlri)
            #print("{}/{}".format(nlri.prefix, nlri.prefix_len))
            pattrs = []
            for attr_name in pb_msg_attrs(path):
                if attr_name == "nlri":
                    continue
                if attr_name == "pattrs":
                    for pattr in path.pattrs:
                        pattr_name = pattr.type_url.split(".")[-1]
                        pattr_cls = getattr(attribute_pb2, pattr_name, None)
                        if pattr_cls:
                            pattr_obj = pattr_cls()
                            pattr.Unpack(pattr_obj)
                            for k in pb_msg_attrs(pattr_obj):
                                if k == "communities":
                                    v = [ str("{}:{}".format(int("0xffff",16)&c>>16, int("0xffff",16)&c)) for c in getattr(pattr_obj, k, []) ]
                                    subnet_info['communities'] = v
                                    if CIDR_COMM in subnet_info['communities']:
                                        subnet_info['found'] = True
                                    if SCRUB_COMM in subnet_info['communities']:
                                        subnet_info['community_scrub'] = True
    #print(subnet_info)
    if subnet_info['found']:
        if scrub_community:
            if subnet_info['community_scrub']:
                return True
        elif subnet_info['found']:
            return True
    else:
        return False






def main():
    #connect to API
    channel = grpc.insecure_channel('127.0.0.1:50051')
    stub = gobgp_pb2_grpc.GobgpApiStub(channel)


    parser = argparse.ArgumentParser(prog=sys.argv[0], )
    parser.add_argument('ip', action='store')
    parser_afg = parser.add_mutually_exclusive_group(required=True)
    parser_afg.add_argument('-a', action='store_const', dest="todo", const='add', help="Add Prefix to Scrubbing")
    parser_afg.add_argument('-r', action='store_const', dest="todo", const='remove', help="Remove prefix from Scrubbing")
    argopts = parser.parse_args()
    ip = argopts.ip.split('/')[0] + '/32'



    subnet = get_subnet(ip)
    if argopts.todo =='add':
        print(f'DDoS Attack start , action add for {ip} ')
        while not go_bgp_check_subnet(stub,subnet):
            print('Subnet not found ... starting bgp inject workflow')
            supernet = go_bgp_check_supernet(stub,subnet)
            if supernet['found']:
                print(f'found supernet {supernet["route"]} ... inject {subnet} subnet with next-hop {supernet["next-hop"]}')
                go_bgp_subnet(stub,subnet,supernet['next-hop'])
            
            else:
                print('Supernet not found ... exiting')
                sys.exit()
        #configure prefix-list regardless if it's a new route or not 
        print(f'*** set policy-options policy-statement PXL-DDOS-SCRUB-PERMIT {subnet}')
        print(f'*** set policy-options policy-statement PXL-DDOS-ALL-REJECT {subnet}')
    elif argopts.todo  =='remove':
        print(f'DDoS Attack stop , action remove for {ip} ')
        if go_bgp_check_subnet(stub,subnet):
            print(f'found subnet {subnet} ... checking if scrubing community is applied ')
            if go_bgp_check_subnet(stub,subnet,scrub_community=True):
                print(f'found subnet {subnet} ... scrubing community IS applied ')
                go_bgp_subnet(stub,subnet,'0.0.0.0',delete=True)
                print(f'delete subnet {subnet}')
            else:
                print('there is no subnet with scrubbing community found ... nothing to do')
        else:
            print('there is no subnet found ... nothing to do')
            sys.exit()
        #configure prefix-list regardless if it's a new route or not 
        print(f'*** del policy-options policy-statement PXL-DDOS-SCRUB-PERMIT {subnet}')
        print(f'*** del policy-options policy-statement PXL-DDOS-ALL-REJECT {subnet}')

if __name__ == '__main__':
  main()