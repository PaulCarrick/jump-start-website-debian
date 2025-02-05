# jump-start-website
Jump Start Website Website Debian Package

To install run the following commands:
curl -fsSL https://jumpstartserver.com:8443/distributions/jump-start-website.asc | sudo gpg --dearmor -o /etc/apt/keyrings/jump-start-website.gpg
echo "deb [signed-by=/etc/apt/keyrings/jump-start-website.gpg] https://jumpstartserver.com:8443/distributions/debian ./" | sudo tee /etc/apt/sources.list.d/jump-start-website.list
sudo apt update
sudo apt install jump-start-website
