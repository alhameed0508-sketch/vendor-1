/**
 * Shared Indian city coordinates and state mappings.
 * Used by IndiaMap, NetworkOverview, and RegionalStatsPanel.
 */

// [longitude, latitude] for react-simple-maps Mercator projection
export const CITY_COORDS = {
  'Mumbai':              [72.8777, 19.0760],
  'Delhi':               [77.1025, 28.7041],
  'Bangalore':           [77.5946, 12.9716],
  'Chennai':             [80.2707, 13.0827],
  'Kolkata':             [88.3639, 22.5726],
  'Hyderabad':           [78.4867, 17.3850],
  'Pune':                [73.8567, 18.5204],
  'Ahmedabad':           [72.5714, 23.0225],
  'Jaipur':              [75.7873, 26.9124],
  'Lucknow':             [80.9462, 26.8467],
  'Surat':               [72.8311, 21.1702],
  'Kochi':               [76.2673, 9.9312],
  'Indore':              [75.8577, 22.7196],
  'Coimbatore':          [76.9558, 11.0168],
  'Nagpur':              [79.0882, 21.1458],
  'Bhopal':              [77.4126, 23.2599],
  'Patna':               [85.1376, 25.6093],
  'Thiruvananthapuram':  [76.9366, 8.5241],
  'Chandigarh':          [76.7794, 30.7333],
  'Guwahati':            [91.7362, 26.1445],
  // Additional cities from demo data
  'Madurai':             [78.1198, 9.9252],
  'Trichy':              [78.6569, 10.7905],
  'Mysore':              [76.6394, 12.2958],
  'Warangal':            [79.5941, 17.9784],
};

export const CITY_TO_STATE = {
  'Mumbai':              'Maharashtra',
  'Pune':                'Maharashtra',
  'Nagpur':              'Maharashtra',
  'Chennai':             'Tamil Nadu',
  'Coimbatore':          'Tamil Nadu',
  'Madurai':             'Tamil Nadu',
  'Trichy':              'Tamil Nadu',
  'Bangalore':           'Karnataka',
  'Mysore':              'Karnataka',
  'Delhi':               'Delhi',
  'Kolkata':             'West Bengal',
  'Hyderabad':           'Telangana',
  'Warangal':            'Telangana',
  'Ahmedabad':           'Gujarat',
  'Surat':               'Gujarat',
  'Jaipur':              'Rajasthan',
  'Lucknow':             'Uttar Pradesh',
  'Kochi':               'Kerala',
  'Thiruvananthapuram':  'Kerala',
  'Indore':              'Madhya Pradesh',
  'Bhopal':              'Madhya Pradesh',
  'Patna':               'Bihar',
  'Chandigarh':          'Chandigarh',
  'Guwahati':            'Assam',
};
