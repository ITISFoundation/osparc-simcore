build map

curl https://raw.githubusercontent.com/google/material-design-icons/master/iconfont/codepoints | perl -e 'print "{";while (<>){my ($k,$v) = split;print qq{  "$k": "$v",\n}};print "}"' > MaterialIcons-Regular.map
