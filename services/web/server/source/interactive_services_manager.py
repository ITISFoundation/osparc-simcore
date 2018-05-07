import director_proxy

running_services = dict()


def session_connect(session_id):
  running_services[session_id] = list()

def session_disconnected(session_id):
  # let's stop all running interactive services
  running_services_for_session = running_services[session_id]
  for service_session_uuid in running_services_for_session:
    director_proxy.stop_service(service_session_uuid)
  running_services[session_id] = list()

def retrieve_list_of_services():
  try:
    return director_proxy.retrieve_interactive_services()
  except Exception as e:
    return "Failed retrieving list of services: " + str(e)

def start_service(session_id, service_name, service_uuid):
  try:
    result = director_proxy.start_service(service_name, service_uuid)
    running_services[session_id].append(service_uuid)
    return result
  except Exception as e:
    return "Failed starting service " + service_name + ": " + str(e)

def stop_service(session_id, service_uuid):
  try:
    result = director_proxy.stop_service(service_uuid)
    running_services[session_id].remove(service_uuid)
    return result
  except Exception as e:
    return "Failed stopping service " + str(e)
