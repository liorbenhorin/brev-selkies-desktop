"""Offline regression checks; no root access, downloads, or package installs."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'assets/brev-selkies-desktop.sh'
SOURCE = SCRIPT.read_text().removesuffix('main "$@"\n')


def bash(code, **env):
    return subprocess.run(['bash', '-c', SOURCE + '\nLOG_FILE=""\n' + code],
                          env={**os.environ, **env}, text=True, capture_output=True)


class InstallerTests(unittest.TestCase):
    def test_shell_syntax_including_generated_scripts(self):
        subprocess.run(['bash', '-n', str(SCRIPT)], check=True)
        for marker in ('WORKSPACE', 'LAUNCH', 'ROS'):
            body = SOURCE.split("<<'" + marker + "'\n", 1)[1].split('\n' + marker + '\n', 1)[0]
            result = subprocess.run(['bash', '-n'], input=body, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        for target in ('brev-selkies-native-start', 'brev-selkies-user-session'):
            body = SOURCE.split(f"cat > /usr/local/bin/{target} <<'EOF'\n", 1)[1].split('\nEOF', 1)[0]
            result = subprocess.run(['bash', '-n'], input=body, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_native_defaults_are_pinned_and_encoder_is_modern(self):
        result = bash('SELKIES_DEPLOYMENT=native; resolve_install_version; resolve_encoder hardware; resolve_encoder software', SELKIES_ENCODER='')
        self.assertEqual(result.stdout.splitlines(), ['2.1.0', 'h264enc', 'h264enc'])

    def test_container_encoders_unchanged(self):
        result = bash('SELKIES_DEPLOYMENT=container; resolve_encoder hardware; resolve_encoder software', SELKIES_ENCODER='')
        self.assertEqual(result.stdout.splitlines(), ['nvh264enc', 'x264enc'])

    def test_ros_distro_matches_ubuntu(self):
        result = bash('ubuntu_version() { echo 22.04; }; workspace_ros_distro; ubuntu_version() { echo 24.04; }; workspace_ros_distro')
        self.assertEqual(result.stdout.splitlines(), ['humble', 'jazzy'])

    def test_old_runtime_rejected_before_install(self):
        result = bash('validate_config', SELKIES_DEPLOYMENT='native', SELKIES_NATIVE_VERSION='1.6.2')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('requires a Selkies 2.x', result.stdout)

    def test_healthcheck_sends_credentials_and_timeout(self):
        with tempfile.TemporaryDirectory() as temp:
            result = bash('curl() { printf "%s\\n" "$@" > "$CHECK_ARGS"; }; healthcheck',
                          CHECK_ARGS=temp + '/args', SELKIES_ENABLE_BASIC_AUTH='true',
                          REMOTE_DESKTOP_PASSWORD='a $ tricky password')
            self.assertEqual(result.returncode, 0, result.stderr)
            args = Path(temp, 'args').read_text().splitlines()
            self.assertIn('ubuntu:a $ tricky password', args)
            self.assertIn('--max-time', args)

    def run_main(self, deployment='native', enabled='1', fail=''):
        stubs = '''
require_root() { :; }
validate_config() { :; }
apt_install() { :; }
resolve_install_version() { echo 2.1.0; }
resolve_acceleration() { echo software; }
log_acceleration_resolution() { :; }
log() { :; }
resolve_turn_host() { :; }
configure_ufw() { :; }
require_tcp_port_free() { :; }
prepare_native_runtime() { echo download; if [[ "$FAIL" == download ]]; then return 22; fi; }
stop_existing_deployments() { echo stop; }
install_native_desktop() { echo native; }
install_container_desktop() { echo container; }
healthcheck() { echo health; if [[ "$FAIL" == health ]]; then return 1; fi; }
install_native_workspace() { echo workspace; }
main
'''
        return bash(stubs, SELKIES_DEPLOYMENT=deployment, SELKIES_NATIVE_WORKSPACE=enabled, FAIL=fail)

    def test_workspace_runs_after_healthy_native_desktop(self):
        result = self.run_main()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ['download', 'stop', 'native', 'health', 'workspace'])

    def test_container_and_opt_out_skip_workspace(self):
        for deployment, enabled in [('container', '1'), ('native', '0')]:
            result = self.run_main(deployment, enabled)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('workspace', result.stdout)

    def test_download_failure_does_not_stop_desktop(self):
        result = self.run_main(fail='download')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), ['download'])

    def test_failed_desktop_does_not_install_workspace(self):
        result = self.run_main(fail='health')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('workspace', result.stdout)

    def test_workspace_only_does_not_redeploy(self):
        result = bash('require_root() { :; }; install_native_workspace() { echo workspace; }; main --setup-workspace')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'workspace')

    def test_native_password_serialization(self):
        start = SOURCE.index("  {\n    printf '%s=%q\\n' SELKIES_NATIVE_USER")
        end = SOURCE.index('  chown "root:${native_group}"', start)
        with tempfile.TemporaryDirectory() as temp:
            output = temp + '/native.env'
            code = SOURCE[start:end].replace('/etc/brev-selkies-desktop/native.env', output)
            result = bash('acceleration=software; encoder=h264enc; native_x_server=xvfb\n' + code +
                          f'\nsource {output}\n[[ "$SELKIES_BASIC_AUTH_PASSWORD" == "$REMOTE_DESKTOP_PASSWORD" ]]',
                          REMOTE_DESKTOP_PASSWORD='a space; $(false) $UNSET_VAR "quote"')
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
