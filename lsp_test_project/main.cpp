#include <vector>
#include <iostream>

#define N 22

using greeter = void(*)();
void hi() {
	std::cout << "HI";
}
greeter func() {
	return &hi;	
}

		
int main() {
	func()();
	bool result = N;
	std::vector<int> vec = std::vector<int>(2);
	int gg;
}

int func() {


}