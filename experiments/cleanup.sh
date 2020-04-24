set -x
set -e
for resources in "deploy" "jobs" "pods"
do
    kubectl delete $resources --all --force
done
