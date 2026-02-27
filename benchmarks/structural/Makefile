CXX      := g++
CXXFLAGS := -O2 -std=c++17

TARGET   := beam_solver
SRC      := beam_solver.cpp

.PHONY: all clean run

all: $(TARGET)

$(TARGET): $(SRC)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(SRC)

run: $(TARGET)
	./$(TARGET)

clean:
	rm -f $(TARGET)
