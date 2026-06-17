#!/bin/sh
get () {
    curl -s -A "$1" 'https://fonts.googleapis.com/icon?family=Material+Icons' | perl -n -e 'm/url\((\S+?)\)/ && do { print $1,"\n"}'
}

get 'fallback'
# iphone
get 'Mozilla/5.0 (iPhone; CPU iPhone OS 11_0 like Mac OS X) AppleWebKit/604.1.38 (KHTML, like Gecko) Version/11.0 Mobile/15A372 Safari/604.1'
# edge
get 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/12.246'
# IE10
get 'Mozilla/5.0 (compatible; MSIE 8.0; Windows NT 6.1; Trident/4.0; GTB7.4; InfoPath.2; SV1; .NET CLR 3.3.69573; WOW64; en-US)'

curl https://raw.githubusercontent.com/google/material-design-icons/master/iconfont/codepoints | perl -e 'print "{";while (<>){my ($k,$v) = split;print qq{  "$k": "$v",\n}};print "}"' > MaterialIcons-Regular.map
