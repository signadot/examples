

signadot sb apply -f - <<EOF
name: wundergraph-products
spec:
  cluster: test
  forks:
    - forkOf:
        kind: Deployment
        namespace: wundergraph-demo
        name: products
      customizations:
        images:
          - image: signadot/wundergraph-demo-products_fg:latest
        env:
        - name: PORT
          value: "4004"
EOF


# Once the sandbox is ready, register the feature flag

wgc feature-subgraph create products-662q5j830g2nw \
 --namespace development \
 --routing-url http://products.wundergraph-demo.svc:4004/graphql \
 --subgraph products

wgc subgraph publish products-662q5j830g2nw \
    --namespace development \
    --schema ./pkg/subgraphs/products_fg/subgraph/schema.graphqls

wgc feature-flag create 662q5j830g2nw \
    --namespace development \
    --feature-subgraphs products-662q5j830g2nw \
    --enabled
