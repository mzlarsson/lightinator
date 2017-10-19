import logging
import util
import projectpath

logger = logging.getLogger(__name__)
data = {}
VARIABLE_START_INDICATOR = "{"
VARIABLE_END_INDICATOR = "}"
VALUE_INDICATOR = VARIABLE_START_INDICATOR+"VALUE"+VARIABLE_END_INDICATOR

def setup_events(variables, events):
    data["variables"] = variables
    data["events"] = events
    data["disabled_devices"] = []
    data["state"] = "default"
    
    def accept(name, mod):
        return hasattr(mod, "get_functions") and callable(getattr(mod, "get_functions"))
    modules = util.load_folder_modules(projectpath.FUNC_PATH, accept)
    data["func"] = {}
    for name, module in modules.items():
        data["func"][name] = module.get_functions()
    data["func"]["event"] = {"setstate": set_state, "togglesensor": toggle_sensor}
    
def set_state(state):
    data["state"] = state
    
def toggle_sensor(sensor):
    if sensor in data["disabled_devices"]:
        data["disabled_devices"].remove(sensor)
    else:
        data["disabled_devices"].append(sensor)
    
def is_variable_reference(obj):
    return type(obj) == str and obj[:1] == VARIABLE_START_INDICATOR and obj[-1:] == VARIABLE_END_INDICATOR
    
def get_variable(name):
    if name[:1] == VARIABLE_START_INDICATOR and name[-1:] == VARIABLE_END_INDICATOR:
        name = name[1:-1]
        
    current_val = data["variables"]
    for part in name.split("."):
        try:
            current_val = current_val[part]
        except:
            try:
                current_val = current_val[int(part)]
            except:
                return None
                
    return current_val
    
def prepare_command(cmd, sensor):
    if type(cmd) == dict:
        prep_cmd = {}
        for key, val in cmd.items():
            prep_cmd[key] = prepare_command(val, sensor)
        return prep_cmd
    elif type(cmd) == list:
        prep_cmd = []
        for val in cmd:
            prep_cmd.append(prepare_command(val, sensor))
        return prep_cmd
    elif type(cmd) == str:
        if cmd == VALUE_INDICATOR:
            return sensor.get_value()
        elif is_variable_reference(cmd):
            return prepare_command(get_variable(cmd), sensor)
            
    return cmd
    
def state_exists():
    return data["events"].get(data["state"]) is not None
    
def command_exists(trigger):
    return data["events"][data["state"]].get(trigger) is not None
    
    
def announce_event(sensor, event_name):
    disabled = sensor.get_id() in data["disabled_devices"]
    trigger = sensor.get_id()+"."+event_name
    
    # use default actions if specific are not specified for this state
    state = "default"
    if state_exists() and command_exists(trigger):
        state = data["state"]
        
    commands = data["events"][state].get(trigger, [])
    if not type(commands) == list:
        commands = [commands]
    for command in commands:
        prepared_command = prepare_command(command, sensor)
        if (not disabled or command["command"] == "togglesensor") and sensor.check_valid(event_name, prepared_command):
            run_command(prepared_command)
        else:
            logger.debug("Stopped command from being run")
        
        
def run_command(command):
    logger.info("Running command : %s", command)
    try:
        module = data["func"][command["module"]]
        func = module[command["command"]]
        params = {key:value for (key, value) in command.items() if not key == "module" and not key == "command"}
        func(**params)
    except:
        logger.warning("Could not run function", exc_info=True)
