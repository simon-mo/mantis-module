set -e

output_arr=()

build_in_dir() {
    cd $1
    SHA=$(docker build . | tail -c 13)
    TRUNC_SHA=$(echo $SHA | head -c 6)
    docker tag $SHA fissure/$2:$TRUNC_SHA
    docker push fissure/$2:$TRUNC_SHA 1>&2
    cd ..

    output="\"$2\":\"fissure/$2:$TRUNC_SHA\""
    output_arr+=("$output")
}

build_in_dir python py
build_in_dir src redis

echo "{"
for o in "${output_arr[@]}"; do
    echo "  $o,"
done
echo "}"