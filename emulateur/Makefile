# emulateur/Makefile — banc PC de l'émulateur (B3)
#   make            compile ./banc, ./banc_r3 et ./test_modes
#   make test       vérifie la trame de test du contrat v1.2
#   make campagne   3 modes x scénarios de donnees/scenarios -> resultats/
#                   (ex. : make campagne ARGS="--reglage s4-regle")
CXX ?= c++
CC  ?= cc
CXXFLAGS = -std=c++11 -O2 -Wall -Iinclude -I../trame/encodeur
CFLAGS   = -O2 -Wall -I../trame/encodeur

ENCODEUR = ../trame/encodeur/encodeur.c

all: banc banc_r3 test_modes

banc: test/banc_pc.cpp src/modes.cpp include/*.h encodeur.o
	$(CXX) $(CXXFLAGS) test/banc_pc.cpp src/modes.cpp encodeur.o -o banc

banc_r3: test/banc_r3.cpp src/rattrapage_r3.cpp src/modes.cpp include/*.h encodeur.o
	$(CXX) $(CXXFLAGS) test/banc_r3.cpp src/rattrapage_r3.cpp src/modes.cpp encodeur.o -o banc_r3

test_modes: test/test_modes.cpp src/modes.cpp include/*.h
	$(CXX) $(CXXFLAGS) test/test_modes.cpp src/modes.cpp -o test_modes

encodeur.o: $(ENCODEUR) ../trame/encodeur/encodeur.h
	$(CC) $(CFLAGS) -c $(ENCODEUR) -o encodeur.o

test: banc
	./banc --test-v12

campagne: banc
	./test/lancer_campagne.sh $(ARGS)

clean:
	rm -f banc banc_r3 test_modes encodeur.o

.PHONY: all test campagne clean