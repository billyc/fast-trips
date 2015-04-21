__copyright__ = "Copyright 2015 Contributing Entities"
__license__   = """
    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""
import Queue
import collections,datetime,os,sys

from .Event import Event
from .Logger import FastTripsLogger
from .Passenger import Passenger
from .Path import Path
from .Stop import Stop
from .TAZ import TAZ
from .Trip import Trip

class Assignment:
    """
    Assignment class.  Documentation forthcoming.
    """

    #: Configuration: Maximum number of iterations to remove capacity violations. When
    #: the transit system is not crowded or when capacity constraint is
    #: relaxed the model will terminate after the first iteration
    ITERATION_FLAG                  = 1

    ASSIGNMENT_TYPE_SIM_ONLY        = 'Simulation Only'
    ASSIGNMENT_TYPE_DET_ASGN        = 'Deterministic Assignment'
    ASSIGNMENT_TYPE_STO_ASGN        = 'Stochastic Assignment'
    #: Configuration: Assignment Type
    #: 'Simulation Only' - No Assignment (only simulation, given paths in the input)
    #: 'Deterministic Assignment'
    #: 'Stochastic Assignment'
    ASSIGNMENT_TYPE                 = ASSIGNMENT_TYPE_DET_ASGN


    #: Configuration: Simulation flag. It should be on for iterative assignment. In a one shot
    #: assignment with simulation flag off, the passengers are assigned to
    #: paths but are not loaded to the network.
    SIMULATION_FLAG                 = True

    #: Configuration: Passenger trajectory output flag. Passengers' path and time will be
    #: reported if this flag is on. Note that the simulation flag should be on for
    #: passengers' time.
    OUTPUT_PASSENGER_TRAJECTORIES   = True

    #: Configuration: Path time-window. This is the time in which the paths are generated.
    #: E.g. with a typical 30 min window, any path within 30 min of the
    #: departure time will be checked.
    PATH_TIME_WINDOW                = datetime.timedelta(minutes = 30)

    #: Configuration: Create skims flag. This is specific to the travel demand models
    #: (not working in this version)
    CREATE_SKIMS                    = False

    #: Configuration: Beginning of the time period for which the skim is required.
    #: (in minutes from start of day)
    #: TODO: change to time?
    SKIM_START_TIME                 = 300

    #: Configuration: End of the time period for which the skim is required
    #: (minutes from start of day)
    SKIM_END_TIME                   = 600

    #: Route choice configuration: Weight of in-vehicle time
    IN_VEHICLE_TIME_WEIGHT          = 1.0

    #: Route choice configuration: Weight of waiting time
    WAIT_TIME_WEIGHT                = 1.77

    #: Route choice configuration: Weight of access walk time
    WALK_ACCESS_TIME_WEIGHT         = 3.93

    #: Route choice configuration: Weight of egress walk time
    WALK_EGRESS_TIME_WEIGHT         = 3.93

    #: Route choice configuration: Weight of transfer walking time
    WALK_TRANSFER_TIME_WEIGHT       = 3.93

    #: Route choice configuration: Weight transfer penalty (minutes)
    TRANSFER_PENALTY                = 47.73

    #: Route choice configuration: Weight of schedule delay (0 - no penalty)
    SCHEDULE_DELAY_WEIGHT           = 0.0

    #: Route choice configuration: Fare in dollars per boarding (with no transfer credit)
    FARE_PER_BOARDING               = 0.0

    #: Route choice configuration: Value of time (dollars per hour)
    VALUE_OF_TIME                   = 999

    #: Route choice configuration: Dispersion parameter in the logit function.
    #: Higher values result in less stochasticity. Must be nonnegative. 
    #: If unknown use a value between 0.5 and 1
    DISPERSION_PARAMETER            = 1.0

    #: Route choice configuration: Use vehicle capacity constraints
    CAPACITY_CONSTRAINT             = False

    #: Use this as the date
    TODAY                           = datetime.date.today()

    @staticmethod
    def read_configuration():
        """
        Read the configuration parameters and override the above
        """
        raise Exception("Not implemented")

    @staticmethod
    def assign_paths(output_dir, FT):
        """
        Finds the paths for the passengers.
        """

        for iteration in range(1,Assignment.ITERATION_FLAG+1):
            FastTripsLogger.info("***************************** ITERATION %d **************************************" % iteration)

            if Assignment.ASSIGNMENT_TYPE == Assignment.ASSIGNMENT_TYPE_SIM_ONLY:
                # read existing paths
                raise Exception("Simulation only not implemented yet")
            elif Assignment.ASSIGNMENT_TYPE == Assignment.ASSIGNMENT_TYPE_DET_ASGN:

                # deterministic assignment
                num_assign_passengers = Assignment.deterministically_assign_passengers(FT, iteration)

            elif Assignment.ASSIGNMENT_TYPE == Assignment.ASSIGNMENT_TYPE_STO_ASGN:
                raise Exception("Stochastic assignment not implemented yet")

            if Assignment.SIMULATION_FLAG == True:
                FastTripsLogger.info("****************************** SIMULATING *****************************")
                Assignment.simulate(FT)

            if Assignment.OUTPUT_PASSENGER_TRAJECTORIES:
                Assignment.print_passenger_paths(FT, output_dir)

            # capacity gap stuff

        # end for loop

    @staticmethod
    def deterministically_assign_passengers(FT, iteration):
        """
        Assigns paths to passengers using deterministic trip-based shortest path (TBSP).
        """
        FastTripsLogger.info("**************************** GENERATING PATHS ****************************")
        start_time          = datetime.datetime.now()
        num_paths_assigned  = 0
        for passenger_id, passenger in FT.passengers.iteritems():

            if not passenger.path.goes_somewhere(): continue

            if iteration > 1:
                # TODO passenger status?
                pass

            if passenger.path.direction == Path.DIR_OUTBOUND:

                asgn_iters = Assignment.find_backwards_trip_based_shortest_path(FT, passenger.path)

            elif passenger.direction == Passenger.DIR_INBOUND:

                asgn_iters = Assignment.find_forwards_trip_based_shortest_path(FT, passenger.path)

            num_paths_assigned += 1

            if num_paths_assigned % 1000 == 0:
                time_elapsed = datetime.datetime.now() - start_time
                FastTripsLogger.info(" %6d / %6d passenger paths assigned.  Time elapsed: %2dh:%2dm:%2ds" % (
                                     num_paths_assigned, len(FT.passengers),
                                     int( time_elapsed.total_seconds() / 3600),
                                     int( (time_elapsed.total_seconds() % 3600) / 60),
                                     time_elapsed.total_seconds() % 60))
                return
            elif num_paths_assigned % 50 == 0:
                FastTripsLogger.debug("%6d / %6d passenger paths assigned" % (num_paths_assigned, len(FT.passengers)))

    @staticmethod
    def find_backwards_trip_based_shortest_path(FT, path):
        """
        Perform backwards (destination to origin) trip-based shortest path search.
        Updates the path information in the given path and returns the number of label iterations required.

        :param FT: fasttrips data
        :type FT: a :py:class:`FastTrips` instance
        :param path: the path to fill in
        :type path: a :py:class:`Path` instance

        """
        # reset stuff?
        dest_taz = FT.tazs[path.destination_taz_id]

        stop_states = {}                    # stop_id -> (label, departure, departure_mode, successor)
        stop_queue  = Queue.PriorityQueue() # (label, stop_id)
        MAX_TIME    = datetime.timedelta(minutes = 999.999)
        stop_done   = set() # stop ids
        trips_used  = set() # trip ids

        # possible egress links
        for stop_id, access_link in dest_taz.access_links.iteritems():
            departure_time       = datetime.datetime.combine(Assignment.TODAY, path.preferred_time) - \
                                   access_link[TAZ.ACCESS_LINK_IDX_TIME]
            stop_states[stop_id] = (access_link[TAZ.ACCESS_LINK_IDX_TIME], # label
                                    departure_time,                        # departure
                                    Path.STATE_MODE_EGRESS,                # departure mode
                                    path.destination_taz_id,               # successor
                                    access_link[TAZ.ACCESS_LINK_IDX_TIME]) # link time
            stop_queue.put( (access_link[TAZ.ACCESS_LINK_IDX_TIME], stop_id ))

        # labeling loop
        label_iterations = 0
        while not stop_queue.empty():
            (current_label, current_stop_id) = stop_queue.get()

            # done conditions for this stop
            if current_stop_id in stop_done: continue
            stop_done.add(current_stop_id)

            current_stop_state = stop_states[current_stop_id]

            # Update by transfer
            # (We don't want to transfer to egress or transfer to a transfer)tg
            if current_stop_state[Path.STATE_IDX_DEPMODE] not in [Path.STATE_MODE_EGRESS,Path.STATE_MODE_TRANSFER]:

                for xfer_stop_id,xfer_attr in FT.stops[current_stop_id].transfers.iteritems():

                    # new_label = length of trip so far if the passenger transfers from this stop
                    new_label       = current_label + xfer_attr[Stop.TRANSFERS_IDX_TIME]
                    departure_time  = current_stop_state[Path.STATE_IDX_DEPARTURE] - xfer_attr[Stop.TRANSFERS_IDX_TIME]

                    #?? check (departure mode, stop) in available capacity
                    old_label       = MAX_TIME
                    if xfer_stop_id in stop_states:
                        old_label   = stop_states[xfer_stop_id][Path.STATE_IDX_LABEL]
                    # print "transfer from %d:  new_label=%s departure_time=%s old_label=%s" % (xfer_stop_id, new_label, departure_time, old_label)

                    if new_label < old_label:
                        stop_states[xfer_stop_id] = (new_label,                 # label,
                                                     departure_time,            # departure time
                                                     Path.STATE_MODE_TRANSFER,  # departure mode
                                                     current_stop_id,           # successor
                                                     xfer_attr[Stop.TRANSFERS_IDX_TIME]) # link time
                        stop_queue.put( (new_label, xfer_stop_id) )

            # Update by trips
            # These are the trips that arrive at the stop in time to depart on time
            valid_trips = FT.stops[current_stop_id].get_trips_arriving_within_time(Assignment.TODAY,
                                                                                   current_stop_state[Path.STATE_IDX_DEPARTURE],
                                                                                   Assignment.PATH_TIME_WINDOW)
            for (trip_id, seq, arrival_time) in valid_trips:

                if trip_id in trips_used: continue
                trips_used.add(trip_id)

                #?? check (departure mode, stop) in available capacity

                wait_time = current_stop_state[Path.STATE_IDX_DEPARTURE] - datetime.datetime.combine(Assignment.TODAY, arrival_time)

                # iterate through the stops before this one
                for seq_num in range(seq-1, 0, -1):
                    possible_board = FT.trips[trip_id].stops[seq_num-1]

                    # new_label = length of trip so far if the passenger boards at this stop
                    board_stop      = possible_board[Trip.STOPS_IDX_STOP_ID]
                    departure_time  = datetime.datetime.combine(Assignment.TODAY, possible_board[Trip.STOPS_IDX_DEPARTURE_TIME])
                    in_vehicle_time = datetime.datetime.combine(Assignment.TODAY, arrival_time) - departure_time
                    new_label       = current_label + in_vehicle_time + wait_time

                    old_label       = MAX_TIME
                    if board_stop in stop_states:
                        old_label   = stop_states[board_stop][Path.STATE_IDX_LABEL]

                    if new_label < old_label:
                        stop_states[board_stop] = (new_label,       # label,
                                                   departure_time,  # departure time
                                                   trip_id,         # departure mode
                                                   current_stop_id, # successor
                                                   in_vehicle_time+wait_time) # link time
                        stop_queue.put( (new_label, board_stop) )

            # Done with this label iteration!
            label_iterations += 1

        # all stops are labeled: let's look at the origin TAZ
        origin_taz = FT.tazs[path.origin_taz_id]
        taz_state  = (MAX_TIME, 0, "", 0)
        for stop_id, access_link in origin_taz.access_links.iteritems():

            if stop_id not in stop_states: continue

            stop_state      = stop_states[stop_id]
            new_label       = stop_state[Path.STATE_IDX_LABEL] + access_link[TAZ.ACCESS_LINK_IDX_TIME]
            departure_time  = stop_state[Path.STATE_IDX_DEPARTURE] - access_link[TAZ.ACCESS_LINK_IDX_TIME]
            #?? check (departure mode, stop) in available capacity

            if new_label < taz_state[Path.STATE_IDX_LABEL]:
                taz_state = (new_label,                 # label,
                             departure_time,            # departure time
                             Path.STATE_MODE_ACCESS,    # departure mode
                             stop_id,                   # successor
                             access_link[TAZ.ACCESS_LINK_IDX_TIME]) # link time

        # Put results into path
        path.states[path.origin_taz_id] = taz_state
        path
        if taz_state[Path.STATE_IDX_LABEL] != MAX_TIME:

            stop_state = taz_state
            while stop_state[Path.STATE_IDX_DEPMODE] != Path.STATE_MODE_EGRESS:

                stop_id    = stop_state[Path.STATE_IDX_SUCCESSOR]
                stop_state = stop_states[stop_id]
                path.states[stop_id] = stop_state

        return label_iterations

    @staticmethod
    def print_passenger_paths(FT, output_dir):
        """
        Print the passenger paths.
        """
        paths_out = open(os.path.join(output_dir, "ft_output_passengerPaths.dat"), 'w')
        for passenger_id, passenger in FT.passengers.iteritems():
            paths_out.write("%s\t%s\n" % (str(passenger_id), passenger.path.path_str()))
        paths_out.close()

    @staticmethod
    def simulate(FT):
        """
        Actually assign the passengers trips to the vehicles.
        """
        start_time              = datetime.datetime.now()
        events_simulated        = 0
        passengers_arrived      = 0   #: arrived at destination TAZ
        passengers_bumped       = 0

        trip_pax                = collections.defaultdict(list)  # trip_id to current [passenger_ids] on board
        stop_pax                = collections.defaultdict(list)  # stop_id to current [passenger_ids] waiting to board
        passenger_id_to_state   = {}  # state: (current passenger status, current path idx)
        transfer_passengers     = []  # passenger ids for passengers who are currently walking or transfering
        bump_wait               = {}  # (trip_id, stop_id) -> earliest time a bumped passenger started waiting

        passenger_arrivals      = collections.defaultdict(list)  # passenger id to [arrival time] at stop
        passenger_boards        = collections.defaultdict(list)  # passenger id to [board time] at stop
        passenger_alights       = collections.defaultdict(list)  # passenger id to [alight time] at stop

        trip_boards             = collections.defaultdict(list)  # trip_id to [number boards per stop]
        trip_alights            = collections.defaultdict(list)  # trip_id to [number alights per stop]
        trip_dwells             = collections.defaultdict(list)  # trip_id to [dwell times per stop]

        PASSENGER_STATUS_INITIAL    = 0
        PASSENGER_STATUS_WALKING    = 1
        PASSENGER_STATUS_WAITING    = 2
        PASSENGER_STATUS_ON_BOARD   = 3
        PASSENGER_STATUS_BUMPED     = 4 #: bumped: couldn't board because vehicle is full
        PASSENGER_STATUS_ARRIVED    = 5 #: arrived at destination

        # reset
        for passenger_id in FT.passengers.keys():
            if not FT.passengers[passenger_id].path.goes_somewhere():   continue
            if not FT.passengers[passenger_id].path.path_found():       continue

            passenger_id_to_state[passenger_id] = (PASSENGER_STATUS_WALKING, 0)
            transfer_passengers.append(passenger_id)

        for event in FT.events:
            event_datetime = datetime.datetime.combine(Assignment.TODAY, event.event_time)

            if event.event_type == Event.EVENT_TYPE_ARRIVAL:

                # are there alight passengers at this stop?
                num_alights = 0
                for passenger_id in list(trip_pax[event.trip_id]):

                    path_idx    = passenger_id_to_state[passenger_id][1]
                    path_state  = FT.passengers[passenger_id].path.states.items()[path_idx][1]
                    alight_stop = path_state[Path.STATE_IDX_SUCCESSOR]

                    if alight_stop != event.stop_id: continue

                    FastTripsLogger.debug("Event (trip %10d, stop %8d, type %s, time %s)" % 
                                          (int(event.trip_id), int(event.stop_id), event.event_type, 
                                           event.event_time.strftime("%H:%M:%S")))
                    FastTripsLogger.debug("Alighting: --------")
                    FastTripsLogger.debug(FT.passengers[passenger_id].path.path_str())

                    passenger_id_to_state[passenger_id] = (PASSENGER_STATUS_WALKING, path_idx+1)
                    passenger_alights[passenger_id].append(event.event_time)
                    transfer_passengers.append(passenger_id)
                    trip_pax[event.trip_id].remove(passenger_id)
                    num_alights += 1

                    FastTripsLogger.debug("-> Passenger %s: state: %s" % (str(passenger_id), str(passenger_id_to_state[passenger_id])))

                trip_alights[event.trip_id].append(num_alights)

            elif event.event_type == Event.EVENT_TYPE_DEPARTURE:

                # transfer passengers: iterate on a copy so we can remove from the list
                for passenger_id in list(transfer_passengers):

                    path_idx    = passenger_id_to_state[passenger_id][1]
                    path_state  = FT.passengers[passenger_id].path.states.items()[path_idx][1]
                    alight_time = path_state[Path.STATE_IDX_DEPARTURE]
                    walk_time   = path_state[Path.STATE_IDX_LINKTIME]
                    arrive_time = alight_time + walk_time

                    # passenger arrived at boarding stop
                    if event_datetime >= arrive_time:
                        FastTripsLogger.debug("Event (trip %10d, stop %8d, type %s, time %s)" % 
                                              (int(event.trip_id), int(event.stop_id), event.event_type, 
                                               event.event_time.strftime("%H:%M:%S")))
                        FastTripsLogger.debug("Transfer: -------- ")
                        FastTripsLogger.debug(FT.passengers[passenger_id].path.path_str())

                        # arrived at destination
                        if path_state[Path.STATE_IDX_DEPMODE] == Path.STATE_MODE_EGRESS:
                            passenger_id_to_state[passenger_id] = (PASSENGER_STATUS_ARRIVED, path_idx+1)
                            # set end time for path?
                            passengers_arrived += 1

                        else:
                            passenger_id_to_state[passenger_id] = (PASSENGER_STATUS_WAITING, path_idx+1)
                            board_stop  = path_state[Path.STATE_IDX_SUCCESSOR]
                            stop_pax[board_stop].append(passenger_id)
                            passenger_arrivals[passenger_id].append(arrive_time)

                        transfer_passengers.remove(passenger_id)
                        FastTripsLogger.debug("-> Passenger %s: state: %s" % (str(passenger_id), str(passenger_id_to_state[passenger_id])))

                # board passengers at this stop
                num_boards = 0
                for passenger_id in list(stop_pax[event.stop_id]):

                    available_capacity = FT.trips[event.trip_id].capacity - len(trip_pax[event.trip_id])

                    if available_capacity == 0:

                        FastTripsLogger.debug("Event (trip %10d, stop %8d, type %s, time %s)" % 
                                              (int(event.trip_id), int(event.stop_id), event.event_type, 
                                               event.event_time.strftime("%H:%M:%S")))
                        FastTripsLogger.debug("Bumping: --------")
                        FastTripsLogger.debug(FT.passengers[passenger_id].path.path_str())

                        passenger_id_to_state[passenger_id] = (PASSENGER_STATE_BUMPED, -1)

                        # update bump_wait
                        if (((event.trip_id, event.stop_id) not in bump_wait) or \
                             (bump_wait[(event.trip_id, event.stop_id)] > passenger_arrivals[passenger_id][-1])):
                            bump_wait[(event.trip_id, event.stop_id)] = passenger_arrivals[passenger_id][-1]

                        passengers_bumped += 1

                        FastTripsLogger.debug("-> Passenger %s: state: %s" % (str(passenger_id), str(passenger_id_to_state[passenger_id])))
                    else:

                        FastTripsLogger.debug("Event (trip %10d, stop %8d, type %s, time %s)" % 
                                              (int(event.trip_id), int(event.stop_id), event.event_type, 
                                               event.event_time.strftime("%H:%M:%S")))
                        FastTripsLogger.debug("Boarding: --------")
                        FastTripsLogger.debug(FT.passengers[passenger_id].path.path_str())

                        trip_pax[event.trip_id].append(passenger_id)
                        passenger_id_to_state[passenger_id] = (PASSENGER_STATUS_ON_BOARD, passenger_id_to_state[passenger_id][1])
                        passenger_boards[passenger_id].append(event.event_time)
                        num_boards += 1

                        FastTripsLogger.debug("-> Passenger %s: state: %s" % (str(passenger_id), str(passenger_id_to_state[passenger_id])))
                    # remove passenger from waiting list
                    stop_pax[event.stop_id].remove(passenger_id)

                trip_boards[event.trip_id].append(num_boards)

                # calculateDwellTime
                trip_dwells[event.trip_id].append(FT.trips[event.trip_id].calculate_dwell_time(trip_boards[event.trip_id][-1],
                                                                                               trip_alights[event.trip_id][-1]))

            events_simulated += 1
            if events_simulated % 1000 == 0:
                time_elapsed = datetime.datetime.now() - start_time
                FastTripsLogger.info(" %6d / %6d events simulated.  Time elapsed: %2dh:%2dm:%2ds" % (
                                     events_simulated, len(FT.events),
                                     int( time_elapsed.total_seconds() / 3600),
                                     int( (time_elapsed.total_seconds() % 3600) / 60),
                                     time_elapsed.total_seconds() % 60))
                return
            elif events_simulated % 50 == 0:
                FastTripsLogger.debug("%6d / %6d events simulated" % (events_simulated, len(FT.events)))