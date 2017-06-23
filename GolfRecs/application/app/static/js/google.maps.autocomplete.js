var placeSearch, autocomplete;
var componentForm = {
  locality: 'long_name',
  administrative_area_level_1: 'long_name',
  country: 'short_name',
  lat: 'long_name',
  lng: 'long_name'
};
function initAutocomplete() {
  autocomplete = new google.maps.places.Autocomplete(
    (document.getElementById('location')),
    {types: ['(cities)']});
    autocomplete.addListener('place_changed', fillInAddress);
}
function fillInAddress() {
  var place = autocomplete.getPlace();
  for (var component in componentForm) {
    document.getElementById(component).value = '';
    document.getElementById(component).disables = false;
  }
  for (var key in Object.keys(place.geometry.location)) {
    if (place.geometry.location.lat) {
      document.getElementById('lat').value = place.geometry.location.lat();
    }
    if (place.geometry.location.lng) {
      document.getElementById('lng').value = place.geometry.location.lng();
    }
  }
  for (var i = 0; i < place.address_components.length; i++) {
    var addressType = place.address_components[i].types[0];
    if (componentForm[addressType]) {
      var val = place.address_components[i][componentForm[addressType]];
      document.getElementById(addressType).value = val;
    }
  }
}
function geolocate() {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(function(position) {
      var geolocation = {
        lat: position.coords.latitude,
        lng: position.coords.longitude
      };
      var circle = new google.maps.Circle({
        center: geolocation,
        radius: position.coords.accuracy
      });
      autocomplete.setBounds(circle.getBounds());
    });
  }
}
