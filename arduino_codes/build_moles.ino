// Define pin ranges and matching logic
const int outputPins[] = {8, 9, 10, 11};  // Pins 7-11
const int inputPins[] = {3, 4, 5, 6};     // Pins 1-5
// index to colors[] = {"yellow, "blue","green","red"};
int count = 0;
int currentIndex = 0; 
int val;
unsigned long previous_time;
bool hasPrinted = false;
String start_command;
bool start_game = false;
void setup() {
  // Initialize output pins
  for (int i = 0; i < 4; i++) {
    pinMode(outputPins[i], OUTPUT);
    digitalWrite(outputPins[i], LOW); 
    randomSeed(analogRead(0));  // A0 is typically used for random seeding
  }

  // Initialize input pins
  for (int i = 0; i < 4; i++) {
    pinMode(inputPins[i], INPUT);  // Set input pins as INPUT
  }

  Serial.begin(115200);  // Initialize serial communication for debugging
  previous_time = millis();
  // digitalWrite(outputPins[currentIndex],HIGH);
}



void loop() {
    if(start_game == false){
    start_command = Serial.readStringUntil('\n');
    start_command.trim();
    if(start_command.equals("s")){
      start_game = true;
    }} 
    if(start_game == true){
    val = digitalRead(inputPins[currentIndex]);   // read the input pin
      if(millis() - previous_time >= 200000000 || val==0){
      previous_time = millis();
      digitalWrite(outputPins[currentIndex], LOW);
      int newIndex;
      do {
        newIndex = random(0,4);
      } while (newIndex == currentIndex || (newIndex==0 && currentIndex==1));
      currentIndex = newIndex;
      Serial.println(currentIndex);
      delay(100);
      digitalWrite(outputPins[currentIndex], HIGH); 
    }
    }
  }
  


    
