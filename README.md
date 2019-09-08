## A command center for Nyzo verifiers

Nyzo Manager aggregates statistics from your miners into a simple web interface

### What is the Nyzo Manager ?

Nyzo manager aggregates all mining statistics into a simple web interface (both standard HTML and API) along with remote reload/stop/reboot capabilities.
Original code written by [Ortis](https://github.com/0rtis/mochimo-farm-manager), changes have been made to repurpose it for Nyzo verifiers. 


### Download, Install & Configuration

Nyzo Manager installation:
1. Clone repository
2. Install [python3](https://www.python.org/downloads/)
	* For Ubuntu use `sudo apt-get update`, `sudo apt-get install python3.6`, `sudo apt-get install python3-pip`
3. Install required module (use`pip3` instead of `pip` in Ubuntu):
	1.  `pip install pycryptodomex` 
	2.  `pip install paramiko`
4. Create a farm configuration file based on the example `example_mining_farm.json`:
	1. `id`: unique ID of the miner
	2. `host`: ip and port for ssh connection. example: `192.168.1.2:22`
	3. `user`: username to use for connection
	4. `password` or `privateKeyPath`: authentication can done by through password or private key
	5. `startCommand`: start command of the miner. It is recommended to use **start.sh** file (or similar syntax) to run your miner (update `MINER_BIN_PATH` before running start.sh). All output will be logged into **miner.log**
	6. `stopCommand`: stop command of the miner. If not specified, a `kill` command is send
	7. `logCommand`: command to retrieve miner's log.
5. *Optional*: encrypt your configuration file using **encryption_file.py** command line tool `python encryption_file.py -m e plain_text_mining_farm_config.json encrypted_mining_farm_config.json`
6. Run the **miner_farm.py** `python miner_farm.py ./html example_mining_farm.json`
7. Access the dashboard http://localhost

### Miner actions
Reload command = sudo supervisorctl reload

Stop command = sudo supervisorctl stop all

Reboot command = sudo reboot


### Nyzo Manager REST API:
* http://localhost/status : farm statistics
* http://localhost/miner?id=minerId : miner statistics
* http://localhost/command?id=minerId&cmd=commandToExecute : execute remote command. At the moment, `cmd=start`, `cmd=stop` and `cmd=reboot` are supported

