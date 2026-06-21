echo "Cleaning up previous builds."
rmdir /s /q dist
rmdir /s /q kontor.egg-info

echo "Incrementing the version number."
python -m ProjectVersion INCREMENT_VERSION MINOR
python -m ProjectVersion INCREMENT_VERSION DEV

echo "Building the package."
python -m build
