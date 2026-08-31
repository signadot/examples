package com.signadot.temporaldemo.signadot;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class SignadotRoutingActivitiesImpl implements SignadotRoutingActivities {
    private static final Logger logger = LoggerFactory.getLogger(SignadotRoutingActivitiesImpl.class);

    private final RoutesClient routesClient;
    private final String workerIdent;

    public SignadotRoutingActivitiesImpl(RoutesClient routesClient, String workerIdent) {
        this.routesClient = routesClient;
        this.workerIdent = workerIdent;
    }

    @Override
    public boolean shouldProcess(String routingKey) {
        boolean should = routesClient.shouldProcess(routingKey);
        logger.debug("[Worker:{}] signadotShouldProcess('{}') -> {}", workerIdent, routingKey, should);
        return should;
    }
}
