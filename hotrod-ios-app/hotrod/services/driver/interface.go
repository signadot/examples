package driver

import (
	"github.com/signadot/hotrod/services/location"
)

type DispatchRequest struct {
	PickupLocation  *location.Location `json:"pickupLocation"`
	DropoffLocation *location.Location `json:"dropoffLocation"`
}

type Driver struct {
	DriverID    string  `json:"driverId"`
	Coordinates string  `json:"coordinates"`
	Rating      float64 `json:"rating"` // Default rating is 0.0 if not available
}
