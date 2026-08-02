#define LEFT_ENCODER A0
#define RIGHT_ENCODER 13

volatile long leftTicks = 0;
volatile long rightTicks = 0;

volatile byte lastPortB;
volatile byte lastPortC;

void setup()
{
  Serial.begin(115200);

  pinMode(LEFT_ENCODER, INPUT_PULLUP);
  pinMode(RIGHT_ENCODER, INPUT_PULLUP);

  lastPortB = PINB;
  lastPortC = PINC;

  // Enable Pin Change Interrupts
  PCICR |= (1 << PCIE0);   // PORTB (D8-D13)
  PCICR |= (1 << PCIE1);   // PORTC (A0-A5)

  // D13 = PB5
  PCMSK0 |= (1 << PCINT5);

  // A0 = PC0
  PCMSK1 |= (1 << PCINT8);

  Serial.println("Encoder Test Started");
}

// D13 Interrupt
ISR(PCINT0_vect)
{
  byte currentPortB = PINB;

  if ((lastPortB & _BV(PB5)) && !(currentPortB & _BV(PB5)))
  {
    rightTicks++;
  }

  lastPortB = currentPortB;
}

// A0 Interrupt
ISR(PCINT1_vect)
{
  byte currentPortC = PINC;

  if ((lastPortC & _BV(PC0)) && !(currentPortC & _BV(PC0)))
  {
    leftTicks++;
  }

  lastPortC = currentPortC;
}

void loop()
{
  static unsigned long timer = 0;

  if (millis() - timer >= 500)
  {
    timer = millis();

    noInterrupts();
    long L = leftTicks;
    long R = rightTicks;
    interrupts();

    Serial.print("Left (A0): ");
    Serial.print(L);
    Serial.print("   Right (D13): ");
    Serial.println(R);
  }
}