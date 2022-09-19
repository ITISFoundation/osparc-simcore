#!/bin/sh
exec sc-pg info | grep --regexp='^Rev: .* (head)$'
