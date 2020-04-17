set -x

cd ..
make
cd experiments

./cleanup.sh

kubectl apply -f master_ctl.yaml
