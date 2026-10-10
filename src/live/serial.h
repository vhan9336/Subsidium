#pragma once
#include <optional>
#include <string>

namespace so::live {

// Minimal POSIX serial port: 8N1, raw, non-blocking, line-oriented.
class SerialPort {
 public:
  ~SerialPort() { close(); }
  bool open(const std::string& path, int baud = 115200);
  void close();
  bool isOpen() const { return fd_ >= 0; }
  // Returns the next complete line if one is buffered.
  std::optional<std::string> readLine();
  bool writeLine(const std::string& line);
  const std::string& error() const { return error_; }

 private:
  int fd_ = -1;
  std::string buf_;
  std::string error_;
};

}  // namespace so::live
