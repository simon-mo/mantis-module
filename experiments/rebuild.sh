set -x

cd ..
make
cd experiments

kubectl delete jobs --all
kubectl apply -f master_ctl.yaml