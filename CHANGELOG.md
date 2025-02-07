# 0.1.9

* Add `ssh_on_server` to check ssh connection (\#29).
* Replace `df` with `psutil.disk_usage` (\#29).
* Remove `triggering` in favor of `success` (\#29).
* Add `service_is_active` to monitor services status (\#29).

# 0.1.8

* Drop check `file_logs` (\#28).
* Add `use_user` attribute to `service_logs` function (\#28).
* Add `checks_runtime` into summary (\#27).

# 0.1.7

* Add `include_login` option (\#23).

# 0.1.6

* Fix `service_logs` and `file_logs` (\#19).

# 0.1.5

* Add `service_logs` and `file_logs` (\#18).

# 0.1.4

* Add retries on `url_json`(\#16)

# 0.1.3

* Add filesystem check (\#14).

# 0.1.2

* Fix recipients-field issue when sending email to multiple recipients (\#12).

# 0.1.1

First version tracked in CHANGELOG.
