set -x
set -e
for resources in "deploy" "jobs" "services" "configmap" "pods"
do
    kubectl delete $resources --all --force
done
