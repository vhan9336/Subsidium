#include "serial.h"

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>

namespace so::live {

static speed_t toSpeed(int baud) {
  switch (baud) {
    case 9600: return B9600;
    case 57600: return B57600;
    case 230400: return B230400;
    default: return B115200;
  }
}

bool SerialPort::open(const std::string& path, int baud) {
  close();
  fd_ = ::open(path.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK);
  if (fd_ < 0) {
    error_ = path + ": " + std::strerror(errno);
    return false;
  }
  termios tty{};
  if (tcgetattr(fd_, &tty) != 0) {
    error_ = std::string("tcgetattr: ") + std::strerror(errno);
    close();
    return false;
  }
  cfmakeraw(&tty);
  cfsetispeed(&tty, toSpeed(baud));
  cfsetospeed(&tty, toSpeed(baud));
  tty.c_cflag |= CLOCAL | CREAD;
  tty.c_cc[VMIN] = 0;
  tty.c_cc[VTIME] = 0;
  if (tcsetattr(fd_, TCSANOW, &tty) != 0) {
    error_ = std::string("tcsetattr: ") + std::strerror(errno);
    close();
    return false;
  }
  error_.clear();
  return true;
}

void SerialPort::close() {
  if (fd_ >= 0) ::close(fd_);
  fd_ = -1;
  buf_.clear();
}

std::optional<std::string> SerialPort::readLine() {
  if (fd_ < 0) return std::nullopt;
  char tmp[256];
  ssize_t n;
  while ((n = ::read(fd_, tmp, sizeof tmp)) > 0) buf_.append(tmp, static_cast<size_t>(n));
  const auto pos = buf_.find('\n');
  if (pos == std::string::npos) {
    if (buf_.size() > 4096) buf_.clear();
    return std::nullopt;
  }
  std::string line = buf_.substr(0, pos);
  buf_.erase(0, pos + 1);
  if (!line.empty() && line.back() == '\r') line.pop_back();
  return line;
}

bool SerialPort::writeLine(const std::string& line) {
  if (fd_ < 0) return false;
  const std::string s = line + "\n";
  return ::write(fd_, s.data(), s.size()) == static_cast<ssize_t>(s.size());
}

}  // namespace so::live
