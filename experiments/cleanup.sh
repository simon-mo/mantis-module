set -x
set -e
for resources in "deploy" "jobs" "pods" "hpa"
do
    kubectl delete $resources --all --force
done
